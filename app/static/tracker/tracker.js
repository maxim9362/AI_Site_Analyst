/**
 * AI Site Analyst - JavaScript Tracker
 *
 * Usage:
 * <script src="https://your-domain.com/static/tracker/tracker.js" data-site-id="site_xxxxxxxxxxxx"></script>
 */
(function() {
  'use strict';

  // Находим текущий script-тег tracker, чтобы читать настройки из data-атрибутов.
  function getTrackerScript() {
    return document.currentScript || document.querySelector('script[data-site-id]');
  }

  // Configuration
  var CONFIG = {
    API_BASE: (function() {
      var script = getTrackerScript();
      if (script) {
        var src = script.src || '';
        var url = new URL(src);
        return url.origin;
      }
      return window.location.origin;
    })(),
    TIME_ON_PAGE_INTERVAL: 15000,
    MAX_TEXT_LENGTH: 120,
    SCROLL_LEVELS: [25, 50, 75, 100],
    BLOCK_VIEW_THRESHOLD: 0.5,
    LOG_LINKS: (function() {
      var script = getTrackerScript();
      return !script || script.getAttribute('data-log-links') !== 'false';
    })()
  };

  // Get site_id from script tag
  function getSiteId() {
    var script = getTrackerScript();
    return script ? script.getAttribute('data-site-id') : null;
  }

  // Generate or read visitor_id from localStorage
  function getVisitorId() {
    var key = 'asa_visitor_id';
    var visitorId = localStorage.getItem(key);
    if (!visitorId) {
      visitorId = 'visitor_' + generateRandomId();
      localStorage.setItem(key, visitorId);
    }
    return visitorId;
  }

  // Generate session_id for current session via sessionStorage
  function getSessionId() {
    var key = 'asa_session_id';
    var sessionId = sessionStorage.getItem(key);
    if (!sessionId) {
      sessionId = 'session_' + generateRandomId();
      sessionStorage.setItem(key, sessionId);
    }
    return sessionId;
  }

  // Generate random hex ID
  function generateRandomId() {
    var chars = '0123456789abcdef';
    var result = '';
    for (var i = 0; i < 12; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
  }

  // Truncate text
  function truncateText(text, maxLength) {
    if (!text) return '';
    text = text.trim();
    return text.length > maxLength ? text.substring(0, maxLength) : text;
  }

  // Send event to server
  function sendEvent(eventType, metadata) {
    var siteId = getSiteId();
    if (!siteId) return;

    var payload = {
      site_id: siteId,
      visitor_id: getVisitorId(),
      session_id: getSessionId(),
      event_type: eventType,
      url: window.location.href,
      path: window.location.pathname,
      title: document.title,
      referrer: document.referrer,
      metadata: metadata || {}
    };

    if (navigator.sendBeacon) {
      var blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      navigator.sendBeacon(CONFIG.API_BASE + '/api/events', blob);
    } else {
      fetch(CONFIG.API_BASE + '/api/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        keepalive: true
      }).catch(function() {});
    }
  }

  // Send page snapshot to server
  function sendPageSnapshot(snapshot) {
    var siteId = getSiteId();
    if (!siteId) return;

    var payload = {
      site_id: siteId,
      visitor_id: getVisitorId(),
      session_id: getSessionId(),
      url: window.location.href,
      path: window.location.pathname,
      title: document.title,
      language: document.documentElement.lang || null,
      headings: snapshot.headings,
      links: snapshot.links,
      buttons: snapshot.buttons,
      forms: snapshot.forms,
      contacts: snapshot.contacts,
      text_blocks: snapshot.textBlocks,
      raw_text: snapshot.rawText
    };

    fetch(CONFIG.API_BASE + '/api/page-snapshots', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).catch(function() {});
  }

  // Показываем адреса найденных ссылок в консоли браузера для быстрой проверки карты страницы.
  function logCollectedLinks(snapshot) {
    if (!CONFIG.LOG_LINKS || !window.console || !snapshot.links.length) return;

    var rows = snapshot.links.map(function(link, index) {
      return {
        number: index + 1,
        text: link.text || '(без текста)',
        href: link.href
      };
    });

    console.groupCollapsed('[AI Site Analyst] Найденные ссылки: ' + rows.length);
    rows.forEach(function(row) {
      console.log('[AI Site Analyst] Ссылка #' + row.number + ': ' + row.href + ' | текст: ' + row.text);
    });
    if (console.table) {
      console.table(rows);
    }
    console.groupEnd();
  }

  // Collect page structure
  function collectPageStructure() {
    var snapshot = {
      headings: [],
      links: [],
      buttons: [],
      forms: [],
      contacts: {
        emails: [],
        phones: [],
        whatsapp_links: [],
        tel_links: [],
        mailto_links: []
      },
      textBlocks: [],
      rawText: ''
    };

    // Collect headings
    var headings = document.querySelectorAll('h1, h2, h3');
    headings.forEach(function(el) {
      snapshot.headings.push({
        tag: el.tagName.toLowerCase(),
        text: truncateText(el.textContent, CONFIG.MAX_TEXT_LENGTH)
      });
    });

    // Collect links
    var links = document.querySelectorAll('a[href]');
    links.forEach(function(el) {
      var href = el.href || '';
      var text = truncateText(el.textContent, CONFIG.MAX_TEXT_LENGTH);

      snapshot.links.push({
        text: text,
        href: href
      });

      // Check for contact links
      if (href.match(/wa\.me|whatsapp|api\.whatsapp\.com/i)) {
        snapshot.contacts.whatsapp_links.push(href);
      }
      if (href.match(/^tel:/i)) {
        snapshot.contacts.tel_links.push(href);
      }
      if (href.match(/^mailto:/i)) {
        snapshot.contacts.mailto_links.push(href);
        var email = href.replace(/^mailto:/i, '').split('?')[0];
        if (email && snapshot.contacts.emails.indexOf(email) === -1) {
          snapshot.contacts.emails.push(email);
        }
      }
    });

    // Collect buttons
    var buttons = document.querySelectorAll('button, input[type="button"], input[type="submit"], [role="button"]');
    buttons.forEach(function(el) {
      snapshot.buttons.push({
        text: truncateText(el.textContent || el.value || '', CONFIG.MAX_TEXT_LENGTH),
        type: el.type || 'button'
      });
    });

    // Collect forms
    var forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
      var fields = [];
      var formFields = form.querySelectorAll('input, textarea, select');
      formFields.forEach(function(field) {
        fields.push({
          name: field.name || '',
          type: field.type || field.tagName.toLowerCase(),
          placeholder: field.placeholder || null
        });
      });

      snapshot.forms.push({
        action: form.action || null,
        method: form.method || null,
        fields: fields
      });
    });

    // Collect contacts from text
    var bodyText = document.body.innerText || '';
    var emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
    var phoneRegex = /[\+]?[(]?[0-9]{1,4}[)]?[-\s\./0-9]{7,15}/g;

    var emails = bodyText.match(emailRegex) || [];
    emails.forEach(function(email) {
      if (snapshot.contacts.emails.indexOf(email) === -1) {
        snapshot.contacts.emails.push(email);
      }
    });

    var phones = bodyText.match(phoneRegex) || [];
    phones.forEach(function(phone) {
      phone = phone.trim();
      if (snapshot.contacts.phones.indexOf(phone) === -1 && phone.length >= 7) {
        snapshot.contacts.phones.push(phone);
      }
    });

    // Collect text blocks
    var blockSelectors = 'section, article, main, header, footer';
    var blocks = document.querySelectorAll(blockSelectors);
    var seenTexts = {};

    blocks.forEach(function(el) {
      var text = (el.innerText || '').trim();
      if (text.length < 20) return;
      if (seenTexts[text]) return;

      seenTexts[text] = true;
      var truncatedText = truncateText(text, 1000);

      snapshot.textBlocks.push({
        tag: el.tagName.toLowerCase(),
        text: truncatedText,
        text_length: truncatedText.length
      });
    });

    // Also collect divs with significant text
    var divs = document.querySelectorAll('div');
    divs.forEach(function(el) {
      var text = (el.innerText || '').trim();
      if (text.length < 100) return;
      if (seenTexts[text]) return;

      // Skip if this div is inside a already collected block
      if (el.closest('section, article, main, header, footer')) return;

      seenTexts[text] = true;
      var truncatedText = truncateText(text, 1000);

      snapshot.textBlocks.push({
        tag: 'div',
        text: truncatedText,
        text_length: truncatedText.length
      });
    });

    // Build raw text
    var rawParts = [];
    snapshot.headings.forEach(function(h) {
      rawParts.push(h.text);
    });
    snapshot.textBlocks.forEach(function(b) {
      rawParts.push(b.text);
    });
    snapshot.rawText = rawParts.join('\n\n');

    // Limit raw text
    if (snapshot.rawText.length > 10000) {
      snapshot.rawText = snapshot.rawText.substring(0, 10000);
    }

    return snapshot;
  }

  // Track pageview
  function trackPageview() {
    sendEvent('pageview', {});
  }

  // Track clicks
  function trackClicks() {
    document.addEventListener('click', function(e) {
      var target = e.target.closest('a, button, [role="button"], input[type="submit"]');
      if (!target) return;

      var metadata = {
        tag: target.tagName.toUpperCase(),
        text: truncateText(target.textContent || target.value || '', CONFIG.MAX_TEXT_LENGTH),
        id: target.id || '',
        class: target.className || ''
      };

      if (target.href) {
        metadata.href = target.href;
      }

      sendEvent('click', metadata);
    });
  }

  // Определяем тип блока по id, class и тексту, чтобы аналитика понимала воронку без ручной разметки.
  function inferBlockCategory(el) {
    var structuralSource = [
      el.id || '',
      el.className || ''
    ].join(' ').toLowerCase();
    var textSource = truncateText(el.innerText || '', 300).toLowerCase();
    var source = structuralSource + ' ' + textSource;

    if (structuralSource.match(/hero/)) return 'hero';
    if (structuralSource.match(/pricing|price/)) return 'pricing';
    if (structuralSource.match(/service|services/)) return 'services';
    if (structuralSource.match(/review|reviews/)) return 'reviews';
    if (structuralSource.match(/faq/)) return 'faq';
    if (structuralSource.match(/contact/)) return 'contacts';
    if (structuralSource.match(/benefit/)) return 'benefits';
    if (structuralSource.match(/about/)) return 'about';
    if (structuralSource.match(/form/)) return 'lead_form';

    if (source.match(/главн|первый экран/)) return 'hero';
    if (source.match(/price|pricing|cost|цен|стоим/)) return 'pricing';
    if (source.match(/service|services|uslug|услуг/)) return 'services';
    if (source.match(/review|reviews|отзыв/)) return 'reviews';
    if (source.match(/faq|вопрос/)) return 'faq';
    if (source.match(/contact|контакт|phone|телефон|whatsapp|email/)) return 'contacts';
    if (source.match(/benefit|преимуществ/)) return 'benefits';
    if (source.match(/about|компани/)) return 'about';
    if (source.match(/form|заявк|консультац|отправить/)) return 'lead_form';

    return 'unknown';
  }

  // Фиксируем первый реальный просмотр каждого крупного блока страницы.
  function trackBlockViews() {
    if (!('IntersectionObserver' in window)) return;

    var observedBlocks = document.querySelectorAll('header, main > section, section, article, footer');
    var sentBlocks = {};

    var observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (!entry.isIntersecting || entry.intersectionRatio < CONFIG.BLOCK_VIEW_THRESHOLD) return;

        var el = entry.target;
        var blockKey = el.id || el.tagName.toLowerCase() + '_' + Array.prototype.indexOf.call(observedBlocks, el);
        if (sentBlocks[blockKey]) return;

        sentBlocks[blockKey] = true;
        sendEvent('block_view', {
          block_id: el.id || '',
          tag: el.tagName.toLowerCase(),
          class: el.className || '',
          category: inferBlockCategory(el),
          text: truncateText(el.innerText || '', CONFIG.MAX_TEXT_LENGTH)
        });
        observer.unobserve(el);
      });
    }, { threshold: CONFIG.BLOCK_VIEW_THRESHOLD });

    observedBlocks.forEach(function(el) {
      observer.observe(el);
    });
  }

  // Отправляем факт отправки формы без значений полей, чтобы не собирать персональные данные.
  function trackFormSubmits() {
    document.addEventListener('submit', function(e) {
      var form = e.target;
      if (!form || form.tagName !== 'FORM') return;

      var fields = [];
      var formFields = form.querySelectorAll('input, textarea, select');
      formFields.forEach(function(field) {
        fields.push({
          name: field.name || '',
          type: field.type || field.tagName.toLowerCase()
        });
      });

      sendEvent('form_submit', {
        form_id: form.id || '',
        action: form.action || '',
        method: form.method || '',
        fields: fields
      });
    });
  }

  // Track scroll depth
  function trackScrollDepth() {
    var sentLevels = {};

    function getScrollPercent() {
      var scrollTop = window.pageYOffset || document.documentElement.scrollTop;
      var scrollHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
      return scrollHeight > 0 ? Math.round((scrollTop / scrollHeight) * 100) : 0;
    }

    window.addEventListener('scroll', function() {
      var percent = getScrollPercent();

      CONFIG.SCROLL_LEVELS.forEach(function(level) {
        if (percent >= level && !sentLevels[level]) {
          sentLevels[level] = true;
          sendEvent('scroll', { depth: level });
        }
      });
    });
  }

  // Track time on page
  function trackTimeOnPage() {
    var startTime = Date.now();

    setInterval(function() {
      var seconds = Math.round((Date.now() - startTime) / 1000);
      sendEvent('time_on_page', { seconds: seconds });
    }, CONFIG.TIME_ON_PAGE_INTERVAL);
  }

  // Track page leave
  function trackPageLeave() {
    var startTime = Date.now();

    function sendLeaveEvent() {
      var seconds = Math.round((Date.now() - startTime) / 1000);
      sendEvent('page_leave', { seconds_on_page: seconds });
    }

    window.addEventListener('beforeunload', sendLeaveEvent);
    window.addEventListener('visibilitychange', function() {
      if (document.visibilityState === 'hidden') {
        sendLeaveEvent();
      }
    });
  }

  // Initialize tracker
  function init() {
    if (!getSiteId()) return;

    trackPageview();

    // Collect and send page structure after page load
    setTimeout(function() {
      var snapshot = collectPageStructure();
      logCollectedLinks(snapshot);
      sendPageSnapshot(snapshot);
    }, 1000);

    trackClicks();
    trackFormSubmits();
    trackBlockViews();
    trackScrollDepth();
    trackTimeOnPage();
    trackPageLeave();
  }

  // Start tracking
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
