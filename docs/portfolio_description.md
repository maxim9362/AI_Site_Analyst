# AI Site Analyst — Portfolio Description

## Коротко

AI Site Analyst — сервис, который подключается к сайту через один JS-скрипт и показывает владельцу бизнеса, где сайт получает трафик, где теряет заявки и что нужно улучшить.

Это не просто счётчик посещений, а product dashboard с аналитикой, Google Search Console данными, AI-отчётами и оценкой сайта 0–100.

## Проблема

У многих малых бизнесов есть сайт, но владелец не понимает:

- сколько людей реально заходит на сайт;
- какие страницы смотрят;
- нажимают ли на WhatsApp, телефон или форму;
- какие запросы приводят людей из Google;
- где сайт теряет потенциальные заявки;
- что нужно исправить в первую очередь.

Обычная аналитика часто слишком сложная. Владельцу бизнеса нужен простой ответ: что работает, что мешает заявкам и что улучшить.

## Решение

AI Site Analyst собирает данные с сайта и превращает их в понятный dashboard.

Система показывает:

- посещения и просмотры страниц;
- клики по важным кнопкам;
- WhatsApp / phone / email / CTA действия;
- начало и отправку форм;
- данные Google Search Console;
- поисковые запросы;
- AI-выводы;
- Site Score 0–100;
- быстрые рекомендации по улучшению сайта.

## Что умеет система

- подключение через tracker.js (одна строка на сайте);
- сбор pageview / click / scroll / time-on-page событий;
- goal tracking: WhatsApp, phone, email, CTA, form_start, form_submit;
- page snapshots и knowledge base по текстам сайта;
- AI-классификация блоков сайта;
- Google Search Console OAuth и real sync;
- SEO summary: clicks, impressions, CTR, position;
- таблица поисковых запросов;
- AI reports с выводами и рекомендациями;
- AI Site Score 0–100 по 5 категориям;
- product dashboard с period switcher (24h / 7d / 30d);
- demo site для проверки.

## Для кого

- владельцы малого бизнеса;
- локальные сервисные компании;
- веб-дизайнеры и разработчики сайтов;
- SEO-специалисты и маркетологи;
- небольшие агентства.

Его можно использовать как дополнительную услугу для клиентов, у которых уже есть сайт, но нет понятной аналитики и AI-рекомендаций.

## Технологии

- Python 3.12, FastAPI, Uvicorn
- PostgreSQL, SQLAlchemy async, Alembic
- Pydantic v2, Jinja2
- Vanilla JavaScript (canvas chart)
- Docker Compose
- Gemini API (AI-отчёты, классификация)
- Google Search Console API (SEO-данные)
- cryptography (Fernet для шифрования tokens)

## Что показывает dashboard

- статус сайта;
- код подключения tracker.js;
- период: 24h / 7d / 30d;
- Site Score с разбивкой по категориям;
- график посещений и SEO-метрик;
- целевые действия и воронка;
- Google Search Console summary;
- таблица поисковых запросов;
- AI-выводы с insights;
- quick wins — что улучшить в первую очередь.

Технические данные спрятаны в отдельный блок для разработчика.

## Google Search Console

- OAuth подключение через Google Cloud Console;
- real sync: clicks, impressions, CTR, position по дням;
- поисковые запросы с метриками;
- demo GSC data для локальной проверки;
- GSC данные дневные (24h не поддерживается).

## AI-отчёты

AI получает: tracker analytics, цели, воронку, knowledge base, классификации, GSC данные.

Генерирует: summary, main_problem, recommendations, SEO/traffic/conversion insights.

Если GSC данных нет — AI не делает выводы про SEO и прямо пишет об этом.

## Site Score

Rule-based оценка 0–100 по 5 категориям:

- SEO (по данным GSC)
- Трафик (посетители, просмотры)
- Конверсия (цели, формы, воронка)
- Структура (hero, услуги, контакты, CTA, цены, FAQ)
- Доверие (контакты, отзывы, FAQ, о компании)

Общий score — среднее по категориям с данными. Если GSC не подключён — SEO не входит в общий score.

## Демо-сценарий

1. Открыть demo site
2. Показать tracker.js — одна строка
3. Сделать действия: WhatsApp, телефон, CTA, форма
4. Открыть dashboard
5. Показать цели и воронку
6. Показать GSC данные
7. Показать AI-отчёт
8. Показать Site Score
9. Объяснить бизнес-ценность

Подробный сценарий: `docs/demo_scenario.md`

## Ограничения

- нет полноценной системы пользователей и ролей;
- нет биллинга;
- GSC sync запускается вручную;
- in-memory rate limit подходит только для demo;
- demo site использует тестовые контакты;
- tracker не собирает значения полей форм ради приватности.

## Короткий pitch для партнёров

Я делаю AI-инструменты и автоматизацию для сайтов малого бизнеса.

Один из проектов — AI Site Analyst: система, которая подключается к сайту через небольшой JS-код и показывает владельцу бизнеса понятный dashboard: посещения, клики, заявки, поисковые запросы из Google, AI-выводы и оценку сайта.

Это можно добавлять как дополнительную услугу к сайтам, SEO-продвижению, лендингам и маркетинговым проектам.

## GitHub short description

**EN:** AI-powered website analytics dashboard with tracker.js, goal tracking, Google Search Console sync, AI reports and Site Score for business websites.

**RU:** AI-аналитика для бизнес-сайтов: tracker.js, цели, Google Search Console, AI-отчёты и оценка сайта 0–100.
