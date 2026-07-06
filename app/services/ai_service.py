import json
import logging
import re

import google.generativeai as genai

from app.core.config import settings

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """Ты анализируешь текст сайта клиента.

Твоя задача - классифицировать блок сайта.

Используй только переданный текст.
Не придумывай услуги, цены, сроки, гарантии или факты.
Если информации недостаточно, верни category = "unknown".

Верни только JSON без markdown."""

VALID_CATEGORIES = [
    "hero",
    "services",
    "pricing",
    "reviews",
    "faq",
    "contacts",
    "lead_form",
    "cta",
    "benefits",
    "about",
    "unknown",
]

CLASSIFICATION_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": VALID_CATEGORIES},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
        "detected_items": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["category", "confidence", "reason", "detected_items"],
}

REPORT_PROMPT = """Ты AI-аналитик сайта.

Ты анализируешь сайт клиента, поведение посетителей и, если есть, данные Google Search Console.

Используй только переданные данные:
- тексты сайта;
- классификации блоков;
- события аналитики;
- page snapshots;
- данные Google Search Console (показы, клики, CTR, позиции, запросы);
- явно переданные данные.

Не придумывай цены, услуги, сроки, гарантии, причины или факты.

Если данных недостаточно - так и напиши.

Если Google Search Console данных нет, не делай выводы про:
- показы в Google;
- клики из Google;
- CTR;
- среднюю позицию;
- поисковые запросы;
- SEO-страницы.

Если Google Search Console данные есть, анализируй их вместе с поведением пользователей на сайте.
Обращай внимание на запросы с высокими показами но низким CTR.
Обращай внимание на запросы с хорошей позицией но малым количеством кликов.
Связывай данные GSC с поведением на сайте: какие страницы получают трафик из Google, конвертируются ли посетители из поиска.

Пиши простым языком для владельца малого бизнеса.
Не используй сложные технические термины.

Верни только JSON без markdown."""

REPORT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "main_problem": {"type": "string"},
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "priority": {"type": "string"},
                    "title": {"type": "string"},
                    "reason": {"type": "string"},
                    "expected_effect": {"type": "string"},
                },
                "required": ["priority", "title", "reason", "expected_effect"],
            },
        },
        "funnel": {
            "type": "object",
            "properties": {
                "pageviews": {"type": "integer"},
                "viewed_services": {"type": "integer"},
                "viewed_pricing": {"type": "integer"},
                "clicked_cta": {"type": "integer"},
                "clicked_whatsapp": {"type": "integer"},
                "clicked_phone": {"type": "integer"},
                "submitted_form": {"type": "integer"},
            },
            "required": [
                "pageviews",
                "viewed_services",
                "viewed_pricing",
                "clicked_cta",
                "clicked_whatsapp",
                "clicked_phone",
                "submitted_form",
            ],
        },
        "strengths": {"type": "array", "items": {"type": "string"}},
        "weaknesses": {"type": "array", "items": {"type": "string"}},
        "missing_information": {"type": "array", "items": {"type": "string"}},
        "seo_insights": {"type": "array", "items": {"type": "string"}},
        "traffic_insights": {"type": "array", "items": {"type": "string"}},
        "conversion_insights": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "main_problem", "recommendations", "funnel", "strengths", "weaknesses", "missing_information"],
}


class AIService:
    def __init__(self):
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
        else:
            self.model = None
            logger.warning("Gemini API key not configured; using local fallback analysis")

    def _match_any(self, text: str, markers: tuple[str, ...]) -> bool:
        return any(marker in text for marker in markers)

    def _fallback_classify_text(self, text: str) -> dict:
        normalized = text.lower()
        rules = [
            ("lead_form", ("оставить заявку", "отправить заявку", "ваше имя", "сообщение", "form")),
            ("hero", ("нотариальные услуги", "профессиональные нотариальные")),
            ("pricing", ("цены", "цена", "стоимость", "от 2", "от 3", "₽", "руб", "price", "pricing")),
            ("contacts", ("контакты", "телефон", "whatsapp", "email", "адрес", "mailto:", "tel:")),
            ("reviews", ("отзывы", "рекомендую", "довольна", "клиентов")),
            ("faq", ("часто задаваемые", "какие документы", "сколько времени", "можно ли", "?")),
            ("services", ("наши услуги", "услуги", "удостоверение", "наследственные", "доверенности", "согласия")),
            ("benefits", ("преимущества", "опыт работы", "конфиденциальность", "быстрое оформление")),
            ("about", ("о компании", "более 15 лет", "мы оказываем")),
            ("cta", ("получить консультацию", "оставить заявку", "отправить заявку")),
        ]

        for category, markers in rules:
            if self._match_any(normalized, markers):
                return {
                    "category": category,
                    "confidence": 0.72,
                    "reason": "Локальная классификация по словам и структуре текста.",
                    "detected_items": [marker for marker in markers if marker in normalized][:5],
                }

        return {
            "category": "unknown",
            "confidence": 0.2,
            "reason": "В тексте нет достаточно явных признаков известного блока.",
            "detected_items": [],
        }

    def _extract_funnel_from_context(self, context: str) -> dict:
        # В fallback-режиме берем числа из JSON-контекста аналитики, не придумывая значения.
        funnel = {
            "pageviews": 0,
            "viewed_services": 0,
            "viewed_pricing": 0,
            "clicked_cta": 0,
            "clicked_whatsapp": 0,
            "clicked_phone": 0,
            "submitted_form": 0,
        }
        for key in funnel:
            match = re.search(rf'"{key}"\s*:\s*(\d+)', context)
            if match:
                funnel[key] = int(match.group(1))
        return funnel

    def _fallback_generate_report(self, context: str) -> dict:
        funnel = self._extract_funnel_from_context(context)
        recommendations = []
        weaknesses = []
        strengths = []
        missing_information = []
        seo_insights = []
        traffic_insights = []
        conversion_insights = []

        has_gsc = "GOOGLE SEARCH CONSOLE" in context and "is_connected" in context and '"is_connected": true' in context

        if funnel["pageviews"] == 0:
            missing_information.append("Нет просмотров страниц за выбранный период.")
        if "Цены" in context or "цены" in context or "₽" in context:
            strengths.append("На сайте найдена информация о ценах.")
        else:
            missing_information.append("На сайте не найдена информация о цене.")
        if "WhatsApp" in context or "Телефон" in context or "Email" in context:
            strengths.append("На сайте найдены контактные способы связи.")
        else:
            missing_information.append("На сайте не найдены контактные данные.")

        # Traffic insights.
        if funnel["pageviews"] > 0:
            traffic_insights.append(f"За период зафиксировано {funnel['pageviews']} просмотров страниц.")
        if funnel["viewed_services"] > 0:
            traffic_insights.append(f"Просмотрели услуги: {funnel['viewed_services']} раз.")
        if funnel["viewed_pricing"] > 0:
            traffic_insights.append(f"Просмотрели цены: {funnel['viewed_pricing']} раз.")

        # Conversion insights.
        if funnel["viewed_services"] > 0 and funnel["clicked_cta"] == 0 and funnel["submitted_form"] == 0:
            weaknesses.append("Посетители доходят до услуг, но не фиксируются клики по CTA или отправки формы.")
            conversion_insights.append("Посетители смотрят услуги, но не оставляют заявку.")
            recommendations.append({
                "priority": "high",
                "title": "Усилить CTA после блока услуг",
                "reason": "В аналитике есть просмотры блока услуг, но нет отправок формы или кликов по заявке.",
                "expected_effect": "Больше посетителей перейдут от просмотра услуг к заявке.",
            })

        if funnel["viewed_pricing"] > 0 and funnel["submitted_form"] == 0:
            weaknesses.append("Посетители видят цены, но не отправляют форму.")
            conversion_insights.append("Блок цен просматривается, но конверсия в заявку низкая.")
            recommendations.append({
                "priority": "medium",
                "title": "Добавить кнопку заявки рядом с ценами",
                "reason": "Блок цен просматривается, но форма не отправляется.",
                "expected_effect": "Пользователю будет проще оставить заявку после сравнения цен.",
            })

        if funnel["submitted_form"] > 0:
            strengths.append("Форма заявки работает и уже получила отправку.")
            conversion_insights.append("Форма заявки отправляется — канал работает.")
        if funnel["clicked_whatsapp"] == 0 and "WhatsApp" in context:
            recommendations.append({
                "priority": "medium",
                "title": "Сделать WhatsApp заметнее",
                "reason": "WhatsApp найден на сайте, но кликов по нему в аналитике нет.",
                "expected_effect": "Часть пользователей сможет быстрее перейти к диалогу.",
            })

        # SEO insights (только если GSC данные есть).
        if has_gsc:
            if "нотариус" in context.lower():
                seo_insights.append("Сайт получает показы по нотариальным запросам. Стоит проверить CTR и позиции.")
            seo_insights.append("Данные Google Search Console доступны для анализа SEO-трафика.")

        if not recommendations:
            recommendations.append({
                "priority": "low",
                "title": "Накопить больше данных",
                "reason": "Данных аналитики пока мало для уверенного вывода о проблемном месте.",
                "expected_effect": "Через несколько дней отчет станет точнее.",
            })

        main_problem = weaknesses[0] if weaknesses else "Явная проблема по текущим данным не найдена."
        summary = (
            f"За период зафиксировано {funnel['pageviews']} просмотров страниц, "
            f"{funnel['viewed_services']} просмотров услуг, {funnel['viewed_pricing']} просмотров цен, "
            f"{funnel['clicked_cta']} кликов по CTA и {funnel['submitted_form']} отправок формы."
        )

        return {
            "summary": summary,
            "main_problem": main_problem,
            "recommendations": recommendations,
            "funnel": funnel,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "missing_information": missing_information,
            "seo_insights": seo_insights,
            "traffic_insights": traffic_insights,
            "conversion_insights": conversion_insights,
        }

    async def classify_text(self, text: str) -> dict:
        if not text or len(text.strip()) < 10:
            return {
                "category": "unknown",
                "confidence": 0.0,
                "reason": "Text too short for classification",
                "detected_items": [],
            }

        if not self.model:
            return self._fallback_classify_text(text)

        truncated_text = text[:3000] if len(text) > 3000 else text

        try:
            response = self.model.generate_content(
                [
                    CLASSIFICATION_PROMPT,
                    f"Классифицируй этот блок сайта:\n\n{truncated_text}",
                ],
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=500,
                    response_mime_type="application/json",
                    response_schema=CLASSIFICATION_RESPONSE_SCHEMA,
                ),
            )

            result = json.loads(response.text)

            if result.get("category") not in VALID_CATEGORIES:
                result["category"] = "unknown"

            result["confidence"] = max(0.0, min(1.0, result.get("confidence", 0.0)))

            return result

        except Exception as e:
            logger.error(f"AI classification failed: {e}")
            return self._fallback_classify_text(text)

    async def generate_report(self, context: str) -> dict:
        if not self.model:
            return self._fallback_generate_report(context)

        try:
            # Правило Search Console защищает отчет от SEO-выводов, когда GSC еще не подключен.
            report_prompt = REPORT_PROMPT + """

Дополнительные правила:
- Верни seo_insights если есть GSC данные, пустой массив если нет.
- Верни traffic_insights с выводами по посещениям и поведению.
- Верни conversion_insights с выводами по заявкам и действиям.
- Не придумывай данные которых нет в переданном контексте.
"""
            response = self.model.generate_content(
                [
                    report_prompt,
                    f"Данные для анализа:\n\n{context}",
                ],
                generation_config=genai.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=2000,
                    response_mime_type="application/json",
                    response_schema=REPORT_RESPONSE_SCHEMA,
                ),
            )

            return json.loads(response.text)

        except Exception as e:
            logger.error(f"AI report generation failed: {e}")
            result = self._fallback_generate_report(context)
            result["missing_information"].append(f"Gemini report generation failed: {str(e)[:200]}")
            return result


ai_service = AIService()
