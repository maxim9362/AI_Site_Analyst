document.addEventListener('DOMContentLoaded', function() {
    initThemeToggle();
    initMobileFloatingMenu();
    initInfoPopovers();
    initCopyButtons();
});

function initCopyButtons() {
    var buttons = Array.prototype.slice.call(document.querySelectorAll('[data-copy-target]'));
    if (!buttons.length) return;

    buttons.forEach(function(button) {
        button.addEventListener('click', function() {
            var target = document.getElementById(button.getAttribute('data-copy-target'));
            if (!target) return;
            var value = target.value || target.textContent || '';
            var originalText = button.textContent;

            function markCopied(text) {
                button.textContent = text;
                window.setTimeout(function() {
                    button.textContent = originalText;
                }, 1600);
            }

            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(value).then(function() {
                    markCopied('Скопировано');
                }).catch(function() {
                    target.focus();
                    if (target.select) target.select();
                    markCopied('Скопируйте вручную');
                });
            } else {
                target.focus();
                if (target.select) target.select();
                markCopied('Скопируйте вручную');
            }
        });
    });
}

function initThemeToggle() {
    var buttons = Array.prototype.slice.call(document.querySelectorAll('[data-theme-toggle]'));
    if (!buttons.length) return;

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('aiSiteTheme', theme);
        buttons.forEach(function(button) {
            button.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
        });
        document.querySelectorAll('[data-theme-toggle-icon]').forEach(function(label) {
            label.textContent = theme === 'dark' ? 'Темная' : 'Светлая';
        });
    }

    applyTheme(localStorage.getItem('aiSiteTheme') || document.documentElement.getAttribute('data-theme') || 'light');

    buttons.forEach(function(button) {
        button.addEventListener('click', function() {
            var current = document.documentElement.getAttribute('data-theme') || 'light';
            applyTheme(current === 'dark' ? 'light' : 'dark');
        });
    });
}

function initMobileFloatingMenu() {
    var roots = Array.prototype.slice.call(document.querySelectorAll('[data-mobile-menu]'));
    if (!roots.length) return;

    roots.forEach(function(root) {
        var toggle = root.querySelector('[data-mobile-menu-toggle]');
        var panel = root.querySelector('[data-mobile-menu-panel]');
        if (!toggle || !panel) return;

        function setOpen(isOpen) {
            root.classList.toggle('is-open', isOpen);
            toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        }

        function close() {
            setOpen(false);
        }

        Array.prototype.slice.call(panel.querySelectorAll('a[href]')).forEach(function(link) {
            var href = link.getAttribute('href');
            var path = window.location.pathname;
            if (href && href !== '/' && (path === href || path.indexOf(href + '/') === 0)) {
                link.classList.add('is-active');
            } else if (href === '/' && path === '/') {
                link.classList.add('is-active');
            }
            link.addEventListener('click', close);
        });

        toggle.addEventListener('click', function(event) {
            event.stopPropagation();
            setOpen(!root.classList.contains('is-open'));
        });

        panel.addEventListener('click', function(event) {
            event.stopPropagation();
        });

        document.addEventListener('click', function(event) {
            if (!root.contains(event.target)) close();
        });

        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') close();
        });
    });
}

function initInfoPopovers() {
    var popovers = Array.prototype.slice.call(document.querySelectorAll('details.info-popover'));
    if (!popovers.length) return;

    function isTouchMode() {
        return window.matchMedia && window.matchMedia('(hover: none), (pointer: coarse)').matches;
    }

    function closeOthers(current) {
        popovers.forEach(function(popover) {
            if (popover !== current) popover.open = false;
        });
    }

    popovers.forEach(function(popover) {
        var summary = popover.querySelector('summary');
        if (!summary) return;

        popover.addEventListener('mouseenter', function() {
            if (isTouchMode()) return;
            closeOthers(popover);
            popover.open = true;
        });

        popover.addEventListener('mouseleave', function() {
            if (isTouchMode()) return;
            popover.open = false;
        });

        summary.addEventListener('click', function(event) {
            if (isTouchMode()) return;
            event.preventDefault();
            closeOthers(popover);
            popover.open = true;
        });

        popover.addEventListener('focusout', function(event) {
            if (isTouchMode()) return;
            if (!popover.contains(event.relatedTarget)) {
                popover.open = false;
            }
        });
    });

    document.addEventListener('mousemove', function(event) {
        if (isTouchMode()) return;
        popovers.forEach(function(popover) {
            if (!popover.open) return;
            if (!popover.contains(event.target)) {
                popover.open = false;
            }
        });
    });

    document.addEventListener('touchstart', function(event) {
        var activePopover = event.target.closest && event.target.closest('details.info-popover');
        popovers.forEach(function(popover) {
            if (popover !== activePopover) popover.open = false;
        });
    }, { passive: true });
}
