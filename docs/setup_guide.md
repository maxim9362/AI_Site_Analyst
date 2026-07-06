# Setup Guide — AI Site Analyst

Пошаговая инструкция по запуску проекта локально.

## 1. Клонировать репозиторий

```bash
git clone <repo-url>
cd AI_Site_Analyst
```

## 2. Создать .env

```bash
cp .env.example .env
```

На Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

## 3. Проверить переменные

Открыть `.env` и проверить:

- `DATABASE_URL` — строка подключения к PostgreSQL
- `GEMINI_API_KEY` — ключ Gemini (или оставить пустым для fallback-режима)
- `ADMIN_DASHBOARD_PASSWORD` — пароль admin dashboard

Google OAuth переменные (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`) можно оставить пустыми — приложение запустится без них.

## 4. Запустить Docker

```bash
docker compose up --build -d
```

## 5. Применить миграции

```bash
docker compose exec app alembic upgrade head
```

## 6. Проверить здоровье сервиса

```bash
curl http://localhost:8000/health
```

Ожидаемый ответ:

```json
{"status":"ok","service":"ai-site-analyst"}
```

## 7. Открыть admin dashboard

```text
http://localhost:8000/admin/login
```

Пароль: из `.env` (`ADMIN_DASHBOARD_PASSWORD`).

## 8. Создать клиента

```bash
curl -X POST http://localhost:8000/api/clients \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo Client","email":"demo@example.com"}'
```

## 9. Создать сайт

```bash
curl -X POST http://localhost:8000/api/clients/CLIENT_ID/sites \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo Site","domain":"localhost","allowed_domains":["localhost","127.0.0.1"]}'
```

## 10. Вставить tracker.js

Скопировать Site ID из ответа. Вставить в HTML:

```html
<script src="http://localhost:8000/static/tracker/tracker.js" data-site-id="SITE_ID"></script>
```

## 11. Открыть demo site

```text
http://localhost:8000/demo
```

Открыть demo site с Site ID:

```text
http://localhost:8000/demo?site_id=SITE_ID
```

Или задать `DEMO_SITE_ID=SITE_ID` в `.env`, чтобы `/demo` всегда подключал tracker к этому сайту.

## 12. Сгенерировать demo GSC данные

```bash
curl -X POST "http://localhost:8000/api/sites/SITE_ID/gsc/demo-data?days=30"
```

## 13. Сгенерировать AI report

```bash
curl -X POST "http://localhost:8000/api/sites/SITE_ID/reports/generate?sync=true"
```

## 14. Открыть dashboard

```text
http://localhost:8000/admin/sites/SITE_ID
```

На dashboard будут видны: analytics, цели, GSC данные, AI-отчёт, Site Score.

## Без Gemini API

Если `GEMINI_API_KEY` пустой, включается fallback-режим:
- классификация блоков по правилам;
- отчёт по собранным событиям;
- без AI-генерации.
