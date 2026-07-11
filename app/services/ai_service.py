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

REPORT_PROMPT = """Ты готовишь клиентский AI-отчет по сайту.

Всегда отвечай на русском языке. Не используй английский, если пользователь явно не выбрал английский язык.
Пиши простыми словами для владельца бизнеса, маркетолога или SEO-специалиста.
Не пиши как разработчик и не используй сложный жаргон без объяснения.

Используй только переданные данные:
- тексты сайта;
- структуру страниц;
- действия посетителей, если они есть;
- данные Google Search Console, если они подключены;
- данные скорости и качества сайта, если они переданы;
- явно переданные факты.

Не придумывай цены, услуги, сроки, гарантии, причины, события, заявки, клики или поведение посетителей.

Если нет данных о просмотрах, кликах, заявках или источниках трафика, прямо напиши, что это предварительный вывод по открытой странице и структуре сайта.
В такой ситуации нельзя говорить: "посетители уходят", "люди нажимают", "конверсия низкая", "клиенты выбирают WhatsApp" и любые похожие выводы о реальном поведении.
Можно писать: "по текущим данным действий посетителей пока не видно" или "для точного анализа нужно установить JS-код и накопить данные".

Не показывай клиенту внутренние технические детали:
- Gemini, название модели, provider, API, raw JSON, debug;
- DOM, parser, metadata, raw HTML, crawler;
- page snapshot, knowledge chunk, classification как внутренние сущности.

Если Google Search Console не подключена, не делай выводы про показы, клики из Google, CTR, позиции и поисковые запросы.
Если Search Console подключена, объясняй данные простыми словами: какие запросы дают показы, где мало кликов и что можно улучшить.

Желаемая структура смысла:
- summary: "Краткий вывод" в 2-4 предложениях.
- main_problem: главная проблема простыми словами.
- strengths: что хорошо.
- weaknesses: что мешает заявкам.
- recommendations: что сделать в первую очередь.
- missing_information: каких данных не хватает, без технического шума.

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
        self.model_name = settings.GEMINI_MODEL
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(self.model_name)
        else:
            self.model = None
            logger.warning("Gemini API key not configured; using local fallback analysis")

    def _model_names(self) -> list[str]:
        names = [self.model_name]
        names.extend(
            item.strip()
            for item in settings.GEMINI_FALLBACK_MODELS.split(",")
            if item.strip()
        )
        names.extend(["gemini-flash-lite-latest", "gemini-2.0-flash-lite", "gemini-flash-latest"])
        return list(dict.fromkeys(names))

    def _generate_content(self, parts: list[str], generation_config: genai.GenerationConfig):
        last_error = None
        for model_name in self._model_names():
            try:
                model = self.model if model_name == self.model_name else genai.GenerativeModel(model_name)
                response = model.generate_content(parts, generation_config=generation_config)
                if model_name != self.model_name:
                    logger.warning("Gemini model %s failed; using fallback model %s", self.model_name, model_name)
                    self.model_name = model_name
                    self.model = model
                return response
            except Exception as exc:
                last_error = exc
                logger.warning("Gemini model %s failed: %s", model_name, exc)
        raise last_error or RuntimeError("Gemini generation failed")

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
            weaknesses.append("Данных о действиях посетителей пока нет. Можно дать только предварительный вывод по структуре сайта.")
            missing_information.append("Нет просмотров страниц за выбранный период.")
            recommendations.append({
                "priority": "high",
                "title": "Проверить установку JS-кода и период отчета",
                "reason": "Сервис пока не видит реальные посещения за выбранный период.",
                "expected_effect": "После появления данных отчет покажет клики, заявки, источники трафика и места, где сайт теряет обращения.",
            })
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
            weaknesses.append("Услуги просматривают, но заявок через кнопки или форму пока не видно в данных.")
            conversion_insights.append("После просмотра услуг в данных пока нет перехода к заявке.")
            recommendations.append({
                "priority": "high",
                "title": "Сделать действие после услуг заметнее",
                "reason": "Людям нужно сразу видеть, что делать дальше: оставить заявку, позвонить или написать.",
                "expected_effect": "Путь от просмотра услуг к обращению станет короче и понятнее.",
            })

        if funnel["viewed_pricing"] > 0 and funnel["submitted_form"] == 0:
            weaknesses.append("Цены просматривают, но заявок через форму пока не видно в данных.")
            conversion_insights.append("После просмотра цен в данных пока нет отправки формы.")
            recommendations.append({
                "priority": "medium",
                "title": "Добавить кнопку заявки рядом с ценами",
                "reason": "После цены человеку важно быстро перейти к следующему шагу.",
                "expected_effect": "Пользователю будет проще оставить заявку сразу после сравнения вариантов.",
            })

        if funnel["submitted_form"] > 0:
            strengths.append("Форма заявки работает и уже получила отправку.")
            conversion_insights.append("Форма заявки отправляется — канал работает.")
        if funnel["pageviews"] > 0 and funnel["clicked_whatsapp"] == 0 and "WhatsApp" in context:
            recommendations.append({
                "priority": "medium",
                "title": "Сделать WhatsApp заметнее",
                "reason": "WhatsApp есть на сайте, но за выбранный период кликов по нему пока не видно в данных.",
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
                "reason": "Пока данных мало для уверенного вывода о главной проблеме.",
                "expected_effect": "Через несколько дней отчет сможет точнее показать, что мешает заявкам.",
            })

        main_problem = weaknesses[0] if weaknesses else "Явная проблема по текущим данным не найдена."
        if funnel["pageviews"] == 0:
            summary = (
                "Данных о действиях посетителей пока нет. На основе структуры сайта можно дать только предварительный вывод. "
                "Для точного анализа установите JS-код и дождитесь первых посещений."
            )
        else:
            summary = (
                f"За период зафиксировано {funnel['pageviews']} просмотров страниц, "
                f"{funnel['viewed_services']} просмотров услуг, {funnel['viewed_pricing']} просмотров цен, "
                f"{funnel['clicked_cta']} кликов по CTA и {funnel['submitted_form']} отправок формы."
            )

        return {
            "source": "local_fallback",
            "model": None,
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
            response = self._generate_content(
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
- Верни traffic_insights с выводами по посещениям только если в данных есть реальные посещения.
- Верни conversion_insights с выводами по заявкам и действиям только если в данных есть реальные события.
- Не придумывай данные которых нет в переданном контексте.
- Все поля должны быть на русском языке.
- Не упоминай Gemini, модель, API, JSON, debug или внутренние названия источников.
- Если действий посетителей нет, не делай выводы о поведении и заявках. Напиши, что вывод предварительный и нужен JS-код для точной аналитики.
"""
            response = self._generate_content(
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

            result = json.loads(response.text)
            result["source"] = "gemini"
            result["model"] = self.model_name
            return result

        except Exception as e:
            logger.error(f"AI report generation failed: {e}")
            result = self._fallback_generate_report(context)
            result["source"] = "local_fallback"
            result["model"] = None
            result["missing_information"].append("AI-анализ временно недоступен. Показан быстрый анализ по правилам.")
            return result


ai_service = AIService()
