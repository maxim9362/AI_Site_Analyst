from __future__ import annotations


BOT_SIGNATURES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("Googlebot", "search_engine", ("googlebot", "adsbot-google", "mediapartners-google")),
    ("Bingbot", "search_engine", ("bingbot", "msnbot")),
    ("YandexBot", "search_engine", ("yandexbot", "yandeximages", "yandexmetrika")),
    ("DuckDuckBot", "search_engine", ("duckduckbot",)),
    ("Baiduspider", "search_engine", ("baiduspider",)),
    ("AhrefsBot", "seo_tool", ("ahrefsbot", "ahrefs")),
    ("SemrushBot", "seo_tool", ("semrushbot", "semrush")),
    ("MJ12bot", "seo_tool", ("mj12bot",)),
    ("DotBot", "seo_tool", ("dotbot",)),
    ("FacebookBot", "social_preview", ("facebookexternalhit", "facebot")),
    ("TwitterBot", "social_preview", ("twitterbot",)),
    ("LinkedInBot", "social_preview", ("linkedinbot",)),
    ("TelegramBot", "social_preview", ("telegrambot",)),
    ("WhatsApp Preview", "social_preview", ("whatsapp",)),
    ("PageSpeed/Lighthouse", "performance_tool", ("lighthouse", "pagespeed", "chrome-lighthouse", "gtmetrix")),
    ("Uptime Monitor", "monitoring", ("uptimerobot", "pingdom", "statuscake", "site24x7")),
    ("Generic Bot", "generic", ("bot", "crawler", "spider", "slurp", "headless", "curl", "wget", "python-requests", "scrapy")),
)


def detect_bot(user_agent: str | None) -> dict[str, str | bool | None]:
    normalized = (user_agent or "").strip().lower()
    if not normalized:
        return {"is_bot": False, "bot_name": None, "bot_category": None}

    for bot_name, bot_category, markers in BOT_SIGNATURES:
        if any(marker in normalized for marker in markers):
            return {
                "is_bot": True,
                "bot_name": bot_name,
                "bot_category": bot_category,
            }

    return {"is_bot": False, "bot_name": None, "bot_category": None}
