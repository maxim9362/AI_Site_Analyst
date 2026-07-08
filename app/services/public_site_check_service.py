import asyncio
import ipaddress
import json
import logging
import re
import socket
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
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
        "quick_wins": {"type": "array", "items": {"type": "string"}},
        "next_step": {"type": "string"},
    },
    "required": ["summary", "score", "findings", "quick_wins", "next_step"],
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
        "связаться",
        "консульта",
        "заявк",
        "купить",
        "позвон",
        "whatsapp",
        "contact",
        "call",
        "submit",
    )

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
        if tag == "form":
            self.signals.forms_count += 1
        if tag == "a":
            href = attrs_dict.get("href", "").strip()
            if href.startswith(("tel:", "mailto:")) or "wa.me" in href or "whatsapp" in href.lower():
                self.signals.contact_links.append(href[:160])
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

    def _add_cta(self, text: str):
        normalized = text.lower()
        if any(marker in normalized for marker in self.CTA_MARKERS):
            if text not in self.signals.cta_texts:
                self.signals.cta_texts.append(text[:120])

    def finish(self) -> ExtractedSiteSignals:
        clean_text = " ".join(self._texts)
        self.signals.text_length = len(clean_text)
        self.signals.text_snippets = [item[:240] for item in self._texts if len(item) > 35][:8]
        return self.signals


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
        quick_wins: list[str] = []
        score = 100

        if signals.status_code >= 400:
            score -= 35
            findings.append(f"Сайт отвечает ошибкой HTTP {signals.status_code}.")
        else:
            findings.append(f"Сайт доступен, ответ HTTP {signals.status_code}.")

        if not signals.title:
            score -= 12
            quick_wins.append("Добавьте понятный title: что вы предлагаете и в каком городе/нише.")
        else:
            findings.append(f"Title найден: {signals.title[:90]}.")

        if not signals.meta_description:
            score -= 10
            quick_wins.append("Добавьте meta description, чтобы поисковый сниппет был понятнее.")
        if not signals.h1:
            score -= 12
            quick_wins.append("Добавьте один сильный H1 с главным предложением сайта.")
        if len(signals.h2) < 2:
            score -= 7
            quick_wins.append("Разделите страницу на понятные блоки с H2: услуги, цены, преимущества, контакты.")
        if not signals.cta_texts:
            score -= 14
            quick_wins.append("Добавьте заметную кнопку действия: консультация, заявка, звонок или WhatsApp.")
        if signals.forms_count == 0:
            score -= 8
            quick_wins.append("Добавьте короткую форму заявки или понятную альтернативу связи.")
        if not signals.contact_links:
            score -= 10
            quick_wins.append("Сделайте телефон, email или WhatsApp кликабельными.")
        if signals.text_length < 900:
            score -= 8
            quick_wins.append("Добавьте больше полезного текста: кому помогаете, как проходит услуга, сроки и доверие.")
        if signals.sections_count < 4:
            score -= 6
            quick_wins.append("Усилите структуру первого экрана и основных секций страницы.")

        if signals.cta_texts:
            findings.append(f"Найдены CTA: {', '.join(signals.cta_texts[:3])}.")
        if signals.contact_links:
            findings.append("Есть кликабельные контакты для связи.")
        if signals.forms_count:
            findings.append(f"Найдено форм на странице: {signals.forms_count}.")

        score = max(20, min(100, score))
        findings = findings[:5] or ["На основе открытой страницы удалось получить базовые признаки сайта."]
        quick_wins = quick_wins[:5] or ["Подключите tracker.js, чтобы увидеть реальные клики, заявки и источники трафика."]

        return {
            "url": signals.final_url,
            "status": "ok",
            "summary": (
                "На основе открытой страницы видно, насколько сайт понятен для клиента, "
                "есть ли ключевые SEO-элементы, контакты, формы и призывы к действию. "
                "Для точного анализа поведения посетителей нужно подключить JS-код."
            ),
            "score": score,
            "findings": findings,
            "quick_wins": quick_wins,
            "next_step": "Зарегистрируйтесь и подключите JS-код, чтобы увидеть реальные посетители, клики, заявки и источники трафика.",
        }

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
            "sections_count": signals.sections_count,
            "text_length": signals.text_length,
            "text_snippets": signals.text_snippets[:6],
            "rule_based_score": fallback["score"],
        }
        prompt = """
Ты делаешь бесплатный предварительный анализ сайта без доступа к реальным посетителям.
Верни только JSON:
{
  "summary": "2-4 простых предложения",
  "score": 0-100,
  "findings": ["3-5 фактов по открытой странице"],
  "quick_wins": ["3-5 первых улучшений"],
  "next_step": "короткий CTA зарегистрироваться и подключить JS-код"
}
Не обещай аналитику кликов, заявок или поведения без tracker.js.
Пиши честно: "на основе открытой страницы видно".
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
        return {
            "url": signals.final_url,
            "status": "ok",
            "summary": str(parsed_result.get("summary") or fallback["summary"])[:900],
            "score": max(0, min(100, int(parsed_result.get("score", fallback["score"])))),
            "findings": [str(item)[:220] for item in parsed_result.get("findings", fallback["findings"])][:5],
            "quick_wins": [str(item)[:220] for item in parsed_result.get("quick_wins", fallback["quick_wins"])][:5],
            "next_step": str(parsed_result.get("next_step") or fallback["next_step"])[:300],
        }

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
                "Gemini сейчас не ответил из-за лимита API/quota. "
                "Показан быстрый анализ по правилам; проверьте квоты или billing в Google AI Studio."
            )
        if "api key" in message or "permission" in message or "unauthorized" in message:
            return (
                "Gemini API key не принят или нет доступа к модели. "
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
