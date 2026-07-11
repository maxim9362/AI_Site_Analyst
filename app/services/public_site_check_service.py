import asyncio
import ipaddress
import json
import logging
import re
import socket
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

import google.generativeai as genai

from app.core.config import settings


logger = logging.getLogger(__name__)

MAX_HTML_BYTES = 2 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 10
MAX_REDIRECTS = 4

PUBLIC_SITE_CHECK_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "score": {"type": "integer"},
        "findings": {"type": "array", "items": {"type": "string"}},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "quick_wins": {"type": "array", "items": {"type": "string"}},
        "next_step": {"type": "string"},
    },
    "required": ["summary", "score", "findings", "strengths", "quick_wins", "next_step"],
}


class PublicSiteCheckError(ValueError):
    pass


def _normalize_url(raw_url: str) -> str:
    value = (raw_url or "").strip()
    if not value:
        raise PublicSiteCheckError("Введите адрес сайта.")
    if "://" not in value:
        value = f"https://{value}"
    return value


def _is_blocked_ip(ip_text: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_text)
    except ValueError:
        return True
    return any(
        (
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        )
    )


def validate_public_url(raw_url: str) -> str:
    url = _normalize_url(raw_url)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise PublicSiteCheckError("Можно проверять только обычные сайты с http или https.")
    if not parsed.hostname:
        raise PublicSiteCheckError("Введите корректный адрес сайта.")

    host = parsed.hostname.strip().lower().rstrip(".")
    if host in {"localhost", "0.0.0.0"} or host.endswith(".localhost"):
        raise PublicSiteCheckError("Локальные адреса проверять нельзя.")

    try:
        ipaddress.ip_address(host)
    except ValueError:
        try:
            resolved = socket.getaddrinfo(host, parsed.port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise PublicSiteCheckError("Не удалось найти такой сайт. Проверьте адрес.") from exc
        for row in resolved:
            if _is_blocked_ip(row[4][0]):
                raise PublicSiteCheckError("Этот адрес ведет во внутреннюю сеть, его нельзя проверять публично.")
    else:
        if _is_blocked_ip(host):
            raise PublicSiteCheckError("Локальные и внутренние IP-адреса проверять нельзя.")

    return parsed.geturl()


class SafeRedirectHandler(HTTPRedirectHandler):
    def __init__(self):
        super().__init__()
        self.redirect_count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.redirect_count += 1
        if self.redirect_count > MAX_REDIRECTS:
            raise PublicSiteCheckError("Сайт делает слишком много перенаправлений.")
        validate_public_url(urljoin(req.full_url, newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch_html_sync(url: str) -> tuple[str, int, str]:
    safe_url = validate_public_url(url)
    request = Request(
        safe_url,
        headers={
            "User-Agent": "AI-Site-Analyst-Free-Check/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    opener = build_opener(SafeRedirectHandler())

    try:
        with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            final_url = validate_public_url(response.geturl())
            content_type = (response.headers.get("Content-Type") or "").lower()
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                raise PublicSiteCheckError("Сайт ответил не HTML-страницей. Проверьте главную страницу сайта.")

            body = response.read(MAX_HTML_BYTES + 1)
            if len(body) > MAX_HTML_BYTES:
                raise PublicSiteCheckError("Страница слишком большая для быстрой проверки.")

            charset = response.headers.get_content_charset() or "utf-8"
            html = body.decode(charset, errors="replace")
            return html, getattr(response, "status", 200), final_url
    except HTTPError as exc:
        if exc.code >= 400:
            raise PublicSiteCheckError(f"Сайт ответил ошибкой HTTP {exc.code}.") from exc
        raise PublicSiteCheckError("Сайт недоступен для проверки.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise PublicSiteCheckError("Сайт не ответил вовремя или блокирует запрос.") from exc


@dataclass
class ExtractedSiteSignals:
    title: str = ""
    meta_description: str = ""
    h1: list[str] = field(default_factory=list)
    h2: list[str] = field(default_factory=list)
    cta_texts: list[str] = field(default_factory=list)
    forms_count: int = 0
    contact_links: list[str] = field(default_factory=list)
    contact_link_types: list[str] = field(default_factory=list)
    has_faq: bool = False
    has_demo: bool = False
    has_reviews: bool = False
    has_cases: bool = False
    has_pricing: bool = False
    page_type: str = "business_site"
    contact_quality: str = "none"
    sections_count: int = 0
    text_length: int = 0
    text_snippets: list[str] = field(default_factory=list)
    status_code: int = 0
    final_url: str = ""


class SiteSignalParser(HTMLParser):
    CTA_MARKERS = (
        "заказать",
        "оставить",
        "получить",
        "обсудить",
        "связаться",
        "консульта",
        "сотруднич",
        "внедр",
        "запустить",
        "начать",
        "написать",
        "проект",
        "демо",
        "заявк",
        "купить",
        "позвон",
        "whatsapp",
        "contact",
        "call",
        "demo",
        "submit",
    )
    FAQ_MARKERS = (
        "faq",
        "частые вопросы",
        "часто задаваемые",
        "вопросы партнёров",
        "вопросы партнеров",
        "ответы на вопросы",
        "популярные вопросы",
    )
    REVIEW_MARKERS = ("отзыв", "клиенты говорят", "нам доверяют", "рекомендац")
    CASE_MARKERS = ("кейс", "портфолио", "наши работы", "реализованные проекты", "результаты клиентов", "до/после")
    PRICING_MARKERS = ("цена", "стоимость", "тариф", "пакет", "₪", "$", "€")
    DEMO_MARKERS = ("демо", "demo", "пример", "посмотреть", "запустить")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.signals = ExtractedSiteSignals()
        self._current_tag = ""
        self._ignore_depth = 0
        self._button_text = ""
        self._texts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attrs_dict = {key.lower(): (value or "") for key, value in attrs}
        tag = tag.lower()
        self._current_tag = tag
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignore_depth += 1
        if tag == "meta":
            name = (attrs_dict.get("name") or attrs_dict.get("property") or "").lower()
            if name in {"description", "og:description"} and not self.signals.meta_description:
                self.signals.meta_description = attrs_dict.get("content", "").strip()
        if tag in {"section", "article", "main", "header", "footer"}:
            self.signals.sections_count += 1
            section_text = " ".join(
                (
                    attrs_dict.get("id", ""),
                    attrs_dict.get("class", ""),
                    attrs_dict.get("aria-label", ""),
                )
            ).lower()
            if self._looks_like_faq(section_text):
                self.signals.has_faq = True
        if tag == "form":
            self.signals.forms_count += 1
        if tag == "a":
            href = attrs_dict.get("href", "").strip()
            href_lower = href.lower()
            link_type = self._contact_link_type(href_lower)
            if link_type:
                normalized_href = self._normalize_contact_href(href)
                if normalized_href not in self.signals.contact_links:
                    self.signals.contact_links.append(normalized_href[:160])
                    self.signals.contact_link_types.append(link_type)
        if tag == "input" and attrs_dict.get("type", "").lower() in {"submit", "button"}:
            value = attrs_dict.get("value", "").strip()
            if value:
                self._add_cta(value)
        if tag == "button":
            self._button_text = ""

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._ignore_depth:
            self._ignore_depth -= 1
        if tag == "button" and self._button_text.strip():
            self._add_cta(self._button_text.strip())
            self._button_text = ""
        self._current_tag = ""

    def handle_data(self, data: str):
        if self._ignore_depth:
            return
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return

        if self._current_tag == "title" and not self.signals.title:
            self.signals.title = text[:180]
        elif self._current_tag == "h1":
            self.signals.h1.append(text[:180])
        elif self._current_tag == "h2":
            self.signals.h2.append(text[:180])
        elif self._current_tag in {"a", "button"}:
            self._add_cta(text)
            if self._current_tag == "button":
                self._button_text = f"{self._button_text} {text}".strip()

        self._texts.append(text)
        if self._looks_like_faq(text):
            self.signals.has_faq = True

    def _add_cta(self, text: str):
        normalized = text.lower()
        if any(marker in normalized for marker in self.CTA_MARKERS):
            if text not in self.signals.cta_texts:
                self.signals.cta_texts.append(text[:120])

    def _looks_like_faq(self, text: str) -> bool:
        normalized = text.lower()
        return any(marker in normalized for marker in self.FAQ_MARKERS)

    def _contact_link_type(self, href_lower: str) -> str:
        if href_lower.startswith("tel:"):
            return "phone"
        if href_lower.startswith("mailto:"):
            return "email"
        if "wa.me" in href_lower or "whatsapp" in href_lower:
            return "whatsapp"
        if "telegram" in href_lower or "t.me/" in href_lower:
            return "messenger"
        if "bot" in href_lower:
            return "bot"
        if "contact" in href_lower or "kontakty" in href_lower or "contacts" in href_lower:
            return "contact_page"
        return ""

    def _normalize_contact_href(self, href: str) -> str:
        value = href.strip()
        parsed = urlparse(value)
        if parsed.scheme in {"tel", "mailto"}:
            return f"{parsed.scheme}:{parsed.path.lower()}"
        if parsed.netloc:
            normalized_path = parsed.path.rstrip("/") or "/"
            return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), normalized_path.lower(), "", "", ""))
        return value.split("#", 1)[0].split("?", 1)[0].rstrip("/").lower() or value.lower()

    def finish(self) -> ExtractedSiteSignals:
        clean_text = " ".join(self._texts)
        normalized_text = clean_text.lower()
        self.signals.text_length = len(clean_text)
        self.signals.text_snippets = [item[:240] for item in self._texts if len(item) > 35][:8]
        self.signals.has_demo = self._contains_any(normalized_text, self.DEMO_MARKERS)
        self.signals.has_reviews = self._contains_any(normalized_text, self.REVIEW_MARKERS)
        self.signals.has_cases = self._contains_any(normalized_text, self.CASE_MARKERS)
        self.signals.has_pricing = self._contains_any(normalized_text, self.PRICING_MARKERS)
        self.signals.page_type = self._detect_page_type(normalized_text)
        self.signals.contact_quality = self._detect_contact_quality()
        return self.signals

    def _contains_any(self, normalized_text: str, markers: tuple[str, ...]) -> bool:
        return any(marker in normalized_text for marker in markers)

    def _detect_page_type(self, normalized_text: str) -> str:
        service_markers = ("лендинг", "разработка сайт", "разработке сайт", "создание сайт", "сайт под ключ", "получить предложение")
        partner_markers = ("white-label", "партнер для", "партнёр для", "технический парт", "для дизайнер", "агентств", "сотруднич")
        if self._contains_any(normalized_text, service_markers) and not self._contains_any(normalized_text, ("white-label", "технический парт", "для дизайнер")):
            return "service_landing"
        if self._contains_any(normalized_text, partner_markers):
            return "b2b_partner"
        if self._contains_any(normalized_text, ("платформа", "мастер", "исполнитель", "заказ", "найти специалист", "найти мастера")):
            return "marketplace"
        if self._contains_any(normalized_text, ("заявк", "консультац")):
            return "service_landing"
        return "business_site"

    def _detect_contact_quality(self) -> str:
        link_types = set(self.signals.contact_link_types)
        if self.signals.forms_count > 0 or link_types.intersection({"phone", "email", "whatsapp"}):
            return "strong"
        if link_types.intersection({"messenger", "bot"}):
            return "medium"
        if self.signals.cta_texts and "contact_page" in link_types:
            return "medium"
        if "contact_page" in link_types:
            return "weak"
        if self.signals.cta_texts or self.signals.contact_links:
            return "weak"
        return "none"


class PublicSiteCheckService:
    async def analyze(self, raw_url: str) -> dict:
        html, status_code, final_url = await asyncio.to_thread(_fetch_html_sync, raw_url)
        parser = SiteSignalParser()
        parser.feed(html)
        signals = parser.finish()
        signals.status_code = status_code
        signals.final_url = final_url

        fallback = self._build_rule_based_report(signals)
        if not settings.gemini_configured:
            fallback["analysis_source"] = "rules"
            return fallback

        try:
            ai_report = await asyncio.to_thread(self._build_ai_report, signals, fallback)
            ai_report["analysis_source"] = "gemini"
            return ai_report
        except Exception as exc:
            reason = self._public_ai_error_reason(exc)
            logger.warning("Public site check AI fallback used: %s", self._short_ai_error(exc))
            fallback["analysis_source"] = "rules"
            fallback["findings"].insert(0, reason)
            return fallback

    def _build_rule_based_report(self, signals: ExtractedSiteSignals) -> dict:
        findings: list[str] = []
        strengths: list[str] = []
        quick_wins: list[str] = []
        score = 100
        has_primary_action = bool(signals.cta_texts or signals.contact_links)
        page_type_label = self._page_type_label(signals.page_type)
        contact_quality_label = self._contact_quality_label(signals.contact_quality)

        if signals.status_code >= 400:
            score -= 35
            findings.append(f"Сайт отвечает ошибкой HTTP {signals.status_code}.")
        else:
            findings.append(f"Сайт доступен, ответ HTTP {signals.status_code}.")
        findings.append(f"Тип страницы: {page_type_label}.")

        if not signals.title:
            score -= 12
            quick_wins.append("Добавьте понятный title: что вы предлагаете и в каком городе/нише.")
        else:
            strengths.append("Заголовок страницы найден и помогает понять тему сайта.")

        if not signals.meta_description:
            score -= 5
            quick_wins.append("Добавьте описание страницы для поисковой выдачи, чтобы сниппет был понятнее.")
        else:
            strengths.append("Описание страницы помогает поиску и первому впечатлению.")
        if not signals.h1:
            score -= 12
            quick_wins.append("Добавьте один сильный H1 с главным предложением сайта.")
        else:
            strengths.append("Главный заголовок страницы найден.")
        if len(signals.h2) < 2:
            score -= 4 if signals.page_type == "marketplace" else 7
            quick_wins.append("Разделите страницу на понятные блоки с H2: услуги, цены, преимущества, контакты.")
        else:
            strengths.append("Страница разбита на понятные смысловые блоки.")
        if not signals.cta_texts:
            cta_penalty = 10 if signals.page_type == "b2b_partner" else 14
            if signals.page_type in {"service_landing", "marketplace"}:
                cta_penalty = 8 if signals.page_type == "marketplace" and signals.contact_quality == "medium" else (12 if signals.page_type == "marketplace" else 16)
            if signals.forms_count > 0 or signals.contact_quality == "strong":
                cta_penalty = min(cta_penalty, 6)
            score -= cta_penalty
            quick_wins.append(self._missing_cta_recommendation(signals.page_type))
        else:
            strengths.append("На странице есть понятные призывы к действию.")
        if signals.forms_count == 0:
            if has_primary_action:
                form_penalty = 2 if signals.page_type == "b2b_partner" else 5
                if signals.page_type == "marketplace":
                    form_penalty = 2 if signals.contact_quality in {"medium", "strong"} else 4
                score -= form_penalty
                quick_wins.append(self._form_recommendation(signals.page_type))
            else:
                score -= 8 if signals.page_type in {"service_landing", "marketplace"} else 7
                quick_wins.append("Добавьте короткую форму заявки или понятную альтернативу связи.")
        else:
            strengths.append(f"На странице есть формы для заявки: {signals.forms_count}.")
            if signals.forms_count >= 2:
                quick_wins.append("Проверьте, что все формы на странице корректно отправляют заявки и уведомления приходят без задержки.")
        if not signals.contact_links:
            if signals.cta_texts:
                score -= 3
                quick_wins.append("Проверьте, что основные кнопки ведут на понятный способ связи: форму, мессенджер, email или страницу контактов.")
            else:
                score -= 10
                quick_wins.append("Сделайте телефон, email или WhatsApp кликабельными.")
        elif signals.contact_quality == "weak":
            score -= 3
            quick_wins.append("Усилите путь связи: добавьте форму, мессенджер, телефон или email рядом с главным предложением.")
        elif signals.contact_quality == "medium":
            score -= 1
            strengths.append("Есть рабочий путь к связи, но его можно сделать заметнее или прямее.")
        else:
            strengths.append("Есть сильный путь связи: форма, телефон, email или мессенджер.")
        if signals.text_length < 900:
            score -= 8
            quick_wins.append("Добавьте больше полезного текста: кому помогаете, как проходит услуга, сроки и доверие.")
        if signals.sections_count < 4:
            score -= 6
            quick_wins.append("Усилите структуру первого экрана и основных секций страницы.")
        if not signals.has_faq:
            faq_penalty = 2 if signals.page_type == "b2b_partner" else 4
            score -= faq_penalty
            quick_wins.append(self._faq_recommendation(signals.page_type))
        else:
            strengths.append("Есть раздел частых вопросов, который помогает снять возражения.")
        if not signals.has_cases and not signals.has_reviews:
            if signals.page_type in {"b2b_partner", "service_landing"}:
                score -= 5
                quick_wins.append("Добавьте отзывы, кейсы или примеры работ, чтобы усилить доверие перед заявкой.")
        else:
            strengths.append("На странице есть элементы доверия: отзывы, кейсы, примеры или результаты.")
        if signals.page_type == "service_landing" and not signals.has_pricing:
            score -= 3
            quick_wins.append("Добавьте ориентир по стоимости, пакетам или срокам, чтобы посетителю было проще решиться на заявку.")
        if signals.page_type == "b2b_partner" and not signals.has_demo:
            score -= 5
            quick_wins.append("Для партнёрской страницы полезно показать живое демо или пример результата.")
        elif signals.page_type == "b2b_partner" and signals.has_demo:
            strengths.append("Есть демонстрация или примеры, что особенно важно для партнёрской страницы.")

        if signals.cta_texts:
            findings.append(f"Найдены призывы к действию: {', '.join(signals.cta_texts[:3])}.")
        if signals.contact_links:
            findings.append(f"Путь связи: {contact_quality_label}.")
            findings.append(f"Уникальных контактных путей найдено: {len(signals.contact_links)}.")
        if signals.forms_count:
            findings.append(f"Найдено форм на странице: {signals.forms_count}.")
        if signals.has_faq:
            findings.append("На странице есть блок с частыми вопросами.")

        if signals.page_type == "service_landing" and score > 95:
            score = 95
        score = max(20, min(100, score))
        findings = findings[:5] or ["На основе открытой страницы удалось получить базовые признаки сайта."]
        strengths = strengths[:5] or ["Страница уже даёт базовое понимание предложения."]
        quick_wins = quick_wins[:5] or ["Подключите JS-код, чтобы увидеть реальные клики, заявки и источники трафика."]

        return {
            "url": signals.final_url,
            "status": "ok",
            "summary": (
                f"На основе открытой страницы видно, что это {page_type_label.lower()}. "
                "Оценка учитывает структуру, путь заявки, доверие, разделы страницы и SEO-основу. "
                "Для точного анализа поведения посетителей нужно подключить JS-код."
            ),
            "score": score,
            "findings": findings,
            "strengths": strengths,
            "quick_wins": quick_wins,
            "next_step": "Зарегистрируйтесь и подключите JS-код, чтобы увидеть реальные посетители, клики, заявки и источники трафика.",
        }

    def _page_type_label(self, page_type: str) -> str:
        labels = {
            "b2b_partner": "B2B-страница для партнёров",
            "marketplace": "платформа или маркетплейс",
            "service_landing": "рекламный лендинг услуги",
            "business_site": "бизнес-страница",
        }
        return labels.get(page_type, "бизнес-страница")

    def _contact_quality_label(self, contact_quality: str) -> str:
        labels = {
            "strong": "сильный — форма, телефон, email или WhatsApp доступны прямо на странице",
            "medium": "средний — есть мессенджер, бот или переход к обсуждению",
            "weak": "слабый — есть отдельные ссылки, но путь заявки можно сделать заметнее",
            "none": "не найден",
        }
        return labels.get(contact_quality, "не найден")

    def _missing_cta_recommendation(self, page_type: str) -> str:
        if page_type == "marketplace":
            return "Добавьте два явных действия: для клиента — найти специалиста, для мастера — зарегистрироваться или получить заказ."
        if page_type == "b2b_partner":
            return "Добавьте заметный призыв к обсуждению сотрудничества или просмотру демо."
        return "Добавьте заметную кнопку действия: получить предложение, оставить заявку, позвонить или написать в WhatsApp."

    def _form_recommendation(self, page_type: str) -> str:
        if page_type == "b2b_partner":
            return "Если партнёру удобнее не переходить на отдельную страницу, добавьте короткую форму для обсуждения проекта."
        if page_type == "marketplace":
            return "Добавьте быстрый путь регистрации или заявки прямо на странице, чтобы посетитель не искал следующий шаг."
        return "Добавьте короткую форму заявки рядом с главным предложением, если хотите получать обращения прямо со страницы."

    def _faq_recommendation(self, page_type: str) -> str:
        if page_type == "b2b_partner":
            return "Добавьте раздел частых вопросов о формате сотрудничества, сроках, white-label и ответственности."
        if page_type == "marketplace":
            return "Добавьте раздел частых вопросов о безопасности, оплате, проверке специалистов и процессе работы."
        return "Добавьте раздел частых вопросов о сроках, стоимости, процессе работы и гарантиях."

    def _build_ai_report(self, signals: ExtractedSiteSignals, fallback: dict) -> dict:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        payload = {
            "url": signals.final_url,
            "status_code": signals.status_code,
            "title": signals.title,
            "meta_description": signals.meta_description,
            "h1": signals.h1[:3],
            "h2": signals.h2[:8],
            "cta_texts": signals.cta_texts[:8],
            "forms_count": signals.forms_count,
            "contact_links_count": len(signals.contact_links),
            "contact_link_types": sorted(set(signals.contact_link_types)),
            "contact_quality": signals.contact_quality,
            "has_faq": signals.has_faq,
            "has_demo": signals.has_demo,
            "has_reviews": signals.has_reviews,
            "has_cases": signals.has_cases,
            "has_pricing": signals.has_pricing,
            "page_type": signals.page_type,
            "page_type_label": self._page_type_label(signals.page_type),
            "sections_count": signals.sections_count,
            "text_length": signals.text_length,
            "text_snippets": signals.text_snippets[:6],
            "rule_based_score": fallback["score"],
            "rule_based_strengths": fallback.get("strengths", []),
        }
        prompt = """
Ты делаешь бесплатный предварительный анализ сайта без доступа к реальным посетителям.
Всегда отвечай на русском языке.
Пиши простыми словами для владельца бизнеса, маркетолога или SEO-специалиста.
Не используй английский, если пользователь явно не выбрал английский язык.
Не упоминай Gemini, модель, API, raw JSON, debug, DOM, parser, metadata, raw HTML или crawler.
Не используй сокращения CTA и FAQ в ответе. Пиши по-русски: "призыв к действию" и "раздел частых вопросов".
Не обещай аналитику кликов, заявок или поведения без установленного JS-кода.
Не делай выводы о реальных посетителях: нельзя писать "люди уходят", "клиенты нажимают", "конверсия низкая", если таких данных нет.
Пиши честно: "на основе открытой страницы видно".
Сначала учитывай page_type:
- b2b_partner: важны демо, понятный формат сотрудничества, кейсы/примеры, доверие и путь "обсудить проект".
- marketplace: важны два пути — для клиента и для исполнителя/мастера, доверие, безопасность и быстрый старт.
- service_landing: важны форма, сильный призыв к действию, доверие, отзывы/кейсы, сроки и стоимость.
- business_site: важны ясное предложение, контакты, структура и следующий шаг.
Оценку держи близко к rule_based_score. Не снижай сильно сайт, если есть формы, сильные контакты и понятные призывы к действию.
Сначала отдели факты от проблем. В findings пиши только факты: что реально найдено на странице, включая сильные стороны.
Не записывай найденные плюсы как проблемы. Если H1, title, meta description, призывы к действию, демо, формы или контакты найдены — это плюс или нейтральный факт.
Если cta_texts не пустой, запрещено писать, что на странице нет призыва к действию.
Если forms_count = 0, не называй это критической проблемой, когда есть призыв к действию или контактный путь. Пиши мягко: можно добавить форму, если цель — собирать заявки прямо на странице.
Учитывай тип сайта. Для B2B/партнёрской страницы демо, контактная кнопка и страница обсуждения могут быть нормальным путём заявки.
Если has_faq = true, запрещено советовать "добавить раздел частых вопросов" или "добавить раздел вопросов". Вместо этого можно советовать только усилить существующий раздел частых вопросов конкретными вопросами о сроках, стоимости или формате работы.
Оценивай контакты по contact_quality и contact_link_types. Не называй повторяющиеся ссылки разными способами связи. Если contact_quality = medium, пиши "есть путь к связи через мессенджер, бот или страницу контактов", а не "сильные контактные данные".
Верни только JSON:
{
  "summary": "2-4 простых предложения",
  "score": 0-100,
  "findings": ["3-5 фактов по открытой странице"],
  "strengths": ["2-4 сильные стороны страницы"],
  "quick_wins": ["3-5 первых улучшений"],
  "next_step": "короткий призыв зарегистрироваться и подключить JS-код"
}
"""
        last_error = None
        parsed_result = None
        used_model_name = ""
        for model_name in self._model_names():
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    [prompt, json.dumps(payload, ensure_ascii=False)],
                    generation_config=genai.GenerationConfig(
                        temperature=0.2,
                        max_output_tokens=1200,
                        response_mime_type="application/json",
                        response_schema=PUBLIC_SITE_CHECK_RESPONSE_SCHEMA,
                    ),
                )
                parsed_result = self._parse_ai_json(response.text)
                used_model_name = model_name
                break
            except Exception as exc:
                last_error = exc
                logger.warning("Public site check Gemini model %s failed: %s", model_name, self._short_ai_error(exc))
        if parsed_result is None:
            raise last_error or RuntimeError("Gemini generation failed")

        logger.info("Public site check Gemini response parsed model=%s", used_model_name)
        findings = [self._polish_client_text(str(item))[:220] for item in parsed_result.get("findings", fallback["findings"])][:5]
        strengths = [self._polish_client_text(str(item))[:220] for item in parsed_result.get("strengths", fallback.get("strengths", []))][:5]
        quick_wins = [self._polish_client_text(str(item))[:220] for item in parsed_result.get("quick_wins", fallback["quick_wins"])][:5]
        findings = self._remove_contradictions(findings, signals)
        strengths = self._remove_contradictions(strengths, signals)
        quick_wins = self._remove_contradictions(quick_wins, signals)
        if not findings:
            findings = fallback["findings"][:5]
        if not strengths:
            strengths = fallback.get("strengths", [])[:5]
        if not quick_wins:
            quick_wins = fallback["quick_wins"][:5]
        return {
            "url": signals.final_url,
            "status": "ok",
            "summary": self._polish_client_text(str(parsed_result.get("summary") or fallback["summary"]))[:900],
            "score": max(0, min(100, int(parsed_result.get("score", fallback["score"])))),
            "findings": findings,
            "strengths": strengths,
            "quick_wins": quick_wins,
            "next_step": self._polish_client_text(str(parsed_result.get("next_step") or fallback["next_step"]))[:300],
        }

    def _polish_client_text(self, text: str) -> str:
        replacements = (
            ("FAQ-раздел", "раздел частых вопросов"),
            ("FAQ раздел", "раздел частых вопросов"),
            ("FAQ", "раздел частых вопросов"),
            ("много CTA", "много призывов к действию"),
            ("множество CTA", "множество призывов к действию"),
            ("несколько CTA", "несколько призывов к действию"),
            ("CTA-кноп", "кноп"),
            ("CTA кноп", "кноп"),
            ("CTA", "призывы к действию"),
        )
        result = text
        result = re.sub(r"\s*\(CTA\)", "", result)
        for source, target in replacements:
            result = result.replace(source, target)
        return result

    def _remove_contradictions(self, items: list[str], signals: ExtractedSiteSignals) -> list[str]:
        cleaned: list[str] = []
        for item in items:
            normalized = item.lower()
            if signals.cta_texts and (
                "нет cta" in normalized
                or "отсутствуют cta" in normalized
                or "нет призыв" in normalized
                or "отсутствуют призыв" in normalized
                or "нет кноп" in normalized
                or "отсутствуют кноп" in normalized
            ):
                continue
            if signals.forms_count and (
                "нет форм" in normalized
                or "отсутствуют форм" in normalized
            ):
                continue
            if signals.contact_links and (
                "нет контакт" in normalized
                or "отсутствуют контакт" in normalized
            ):
                continue
            if signals.has_faq and (
                "добавить faq" in normalized
                or "добавить раздел faq" in normalized
                or "добавить faq-раздел" in normalized
                or "добавить блок faq" in normalized
                or "добавить раздел вопросов" in normalized
                or "добавить блок с вопрос" in normalized
                or "добавить частые вопросы" in normalized
                or "добавить раздел частых вопросов" in normalized
                or "добавить блок частых вопросов" in normalized
                or "добавьте раздел частых вопросов" in normalized
                or "добавьте блок частых вопросов" in normalized
                or "добавьте частые вопросы" in normalized
            ):
                continue
            cleaned.append(item)
        return cleaned

    def _parse_ai_json(self, text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))

    def _model_names(self) -> list[str]:
        names = [settings.GEMINI_MODEL]
        names.extend(
            item.strip()
            for item in settings.GEMINI_FALLBACK_MODELS.split(",")
            if item.strip()
        )
        names.extend(["gemini-flash-lite-latest", "gemini-2.0-flash-lite", "gemini-flash-latest"])
        return list(dict.fromkeys(names))

    def _public_ai_error_reason(self, exc: Exception) -> str:
        message = str(exc).lower()
        if "resource_exhausted" in message or "quota" in message or "429" in message:
            return (
                "AI временно не смог подготовить расширенный вывод. "
                "Показан быстрый анализ по правилам; попробуйте повторить проверку позже."
            )
        if "api key" in message or "permission" in message or "unauthorized" in message:
            return (
                "AI временно недоступен. "
                "Показан быстрый анализ по правилам."
            )
        return "AI временно недоступен, поэтому показан быстрый анализ по правилам."

    def _short_ai_error(self, exc: Exception) -> str:
        message = str(exc).lower()
        if "resource_exhausted" in message or "quota" in message or "429" in message:
            return "quota exceeded / rate limit"
        if "not found" in message or "404" in message:
            return "model not available"
        if isinstance(exc, json.JSONDecodeError) or "unterminated string" in message or "json" in message:
            return "invalid json response"
        if "api key" in message or "permission" in message or "unauthorized" in message:
            return "api key or permission error"
        return str(exc).splitlines()[0][:180]
