# AI Site Analyst

AI Site Analyst — веб-сервис аналитики сайта и AI-рекомендаций для бизнеса.

Подключается к сайту через одну строку JavaScript-кода. Собирает поведение посетителей, структуру страниц, целевые действия и данные Google Search Console. Показывает владельцу бизнеса понятный dashboard: откуда приходит трафик, что делают посетители, где теряются заявки и что нужно улучшить в первую очередь.

## Для кого этот проект

- владельцы малого бизнеса;
- локальные сервисные компании;
- веб-дизайнеры и разработчики сайтов;
- SEO-специалисты и маркетологи;
- небольшие агентства.

## Как это работает

```text
1. Сайт добавляется в admin dashboard.
2. Система генерирует Site ID.
3. Site ID вставляется в tracker.js на сайте клиента.
4. tracker.js отправляет события посетителей на backend.
5. Собираются снимки страниц и база знаний.
6. AI классифицирует блоки сайта.
7. Google Search Console подключается (опционально).
8. Dashboard показывает аналитику, SEO, цели и AI-выводы.
9. AI-отчёт объясняет, что улучшить.
```

## Возможности

- отслеживание посещений, кликов, скролла, времени на странице;
- целевые действия: WhatsApp, телефон, email, CTA, формы;
- снимки страниц и база знаний из текстов сайта;
- AI-классификация блоков;
- product dashboard с period switcher (24h / 7d / 30d);
- Performance overview — единый график tracker + GSC данных;
- Google Search Console: OAuth, реальный sync, demo-data;
- поисковые запросы, CTR, средняя позиция;
- AI-отчёты с выводами и рекомендациями;
- AI Site Score 0–100 по 5 категориям;
- admin password gate со signed cookie;
- шифрование OAuth tokens через Fernet.

## Стек технологий

- Python 3.12, FastAPI, Uvicorn
- PostgreSQL, SQLAlchemy async, Alembic
- Pydantic v2, Jinja2
- Vanilla JavaScript (canvas chart, без фреймворков)
- Docker Compose
- Gemini API (AI-отчёты, классификация)
- Google Search Console API (SEO-данные)
- cryptography (Fernet для шифрования токенов)

## Быстрый запуск

```bash
git clone <repo-url>
cd AI_Site_Analyst
cp .env.example .env
docker compose up --build -d
docker compose exec app alembic upgrade head
```

Проверка:

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"ai-site-analyst"}
```

Открыть:

```text
http://localhost:8000/admin/login
```

## Переменные окружения

`.env.example` содержит все переменные с дефолтами. Не коммитить `.env`.

| Переменная | Описание |
|---|---|
| `APP_ENV` | local / production |
| `DEBUG` | true / false |
| `SQL_ECHO` | true / false, verbose SQL logging for local debugging |
| `DEMO_SITE_ID` | Optional default Site ID for `/demo` |
| `DATABASE_URL` | URL подключения PostgreSQL |
| `GEMINI_API_KEY` | API ключ Gemini для AI-отчётов |
| `ADMIN_DASHBOARD_PASSWORD` | Пароль входа в admin dashboard |
| `ADMIN_SESSION_SECRET` | Secret для подписи session cookie |
| `ADMIN_API_KEY` | Optional key for scripts using private admin API endpoints |
| `ADMIN_SESSION_TTL_SECONDS` | Время жизни cookie (default 86400) |
| `ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE` | Max admin login attempts per IP per minute |
| `ENABLE_DEMO_ENDPOINTS` | Включить demo GSC endpoint |
| `ALLOWED_ORIGINS` | CORS origins (* для local) |
| `TRACKER_RATE_LIMIT_PER_MINUTE` | Rate limit для tracker |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret |
| `GOOGLE_REDIRECT_URI` | Google OAuth redirect URI |
| `GOOGLE_SCOPES` | Google API scopes |
| `TOKEN_ENCRYPTION_KEY` | Fernet key для шифрования tokens |

## Admin dashboard

Вход: `http://localhost:8000/admin/login`

Пароль задаётся через `ADMIN_DASHBOARD_PASSWORD`. Cookie подписана HMAC, не хранит пароль. Параметры: `httponly`, `samesite=lax`, `secure=True` в production.

## Tracker.js

Код для вставки на сайт клиента:

```html
<script
  src="http://YOUR_SERVER/static/tracker/tracker.js"
  data-site-id="site_xxxxx">
</script>
```

`site_xxxxx` берётся из admin dashboard. В production заменить домен сервера.

Tracker собирает: pageview, click, scroll, time on page, block view, form start, form submit, goal events (WhatsApp, phone, email, CTA). Значения полей форм НЕ собираются — только метаданные.

## Demo site

Demo site для проверки tracker.js: `http://localhost:8000/demo`

Demo site содержит hero, услуги, цены, преимущества, FAQ, отзывы, контакты, форму. Ниша — нотариальные услуги в Ашдоде.

Для работы tracker.js на demo site:
1. Создать сайт в admin dashboard
2. Скопировать Site ID
3. Открыть `http://localhost:8000/demo?site_id=SITE_ID`

Если нужно, чтобы demo site всегда открывался с одним Site ID без query-параметра, задать `DEMO_SITE_ID=SITE_ID` в `.env`.

Сценарий показа: `docs/demo_scenario.md`

## Product Dashboard

Dashboard показывает:
- шапка: название, домен, Site ID, статус
- tracker.js код для копирования
- Site Score с разбивкой по категориям
- Performance overview — график посещений + SEO
- простая аналитика: посетители, просмотры, клики, цели, воронка
- Google Search Console: показы, клики, CTR, позиция, запросы
- AI-выводы с insights и quick wins

Technical details (события, снимки, классификации) спрятаны в `<details>` для разработчика. Владелец бизнеса видит только понятные данные.

## Google Search Console

### Подключение

1. Настроить Google OAuth в `.env`:
```env
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/api/gsc/oauth/callback
GOOGLE_SCOPES=https://www.googleapis.com/auth/webmasters.readonly
```

2. Начать OAuth: `GET /api/sites/{site_id}/gsc/oauth/start`
3. Список properties: `GET /api/sites/{site_id}/gsc/properties`
4. Sync: `POST /api/sites/{site_id}/gsc/sync?period=30d`

GSC admin endpoints require admin access. OAuth callback `GET /api/gsc/oauth/callback` is public for Google redirect handling and is protected by signed short-lived `state`.

### Endpoints

```bash
# Список GSC properties
curl "http://localhost:8000/api/sites/SITE_ID/gsc/properties"

# Тестовый запрос Search Analytics
curl "http://localhost:8000/api/sites/SITE_ID/gsc/search-analytics/test?period=7d&dimensions=date,query,page&row_limit=100"

# Sync данных в БД
curl -X POST "http://localhost:8000/api/sites/SITE_ID/gsc/sync?period=30d"

# Проверка данных
curl "http://localhost:8000/api/sites/SITE_ID/gsc/summary?period=30d"
curl "http://localhost:8000/api/sites/SITE_ID/gsc/queries?period=30d"
curl "http://localhost:8000/api/sites/SITE_ID/gsc/timeseries?period=30d"
```

### Demo GSC data

Для тестирования без Google OAuth:

```bash
curl -X POST "http://localhost:8000/api/sites/SITE_ID/gsc/demo-data?days=30"
```

Это тестовые данные, не реальные. В production: `ENABLE_DEMO_ENDPOINTS=false`.

GSC данные дневные. Period `24h` не поддерживается для GSC метрик.

## Traffic Sources

AI Site Analyst определяет источники трафика по UTM-параметрам и `document.referrer`.

### Приоритет определения

```text
UTM > referrer > direct
```

### Поддерживаемые источники

- **Google** — organic search (referrer содержит `google.`)
- **Facebook** — social (referrer: `facebook.com`, `fb.com`, `l.facebook.com`, `m.facebook.com`)
- **Instagram** — social (referrer: `instagram.com`, `l.instagram.com`)
- **WhatsApp** — messenger (referrer/utm_source содержит `whatsapp` или `wa.me`)
- **Telegram** — messenger (referrer/utm_source содержит `telegram` или `t.me`)
- **Direct** — прямой заход (referrer пустой, UTM нет)
- **Referral** — другие сайты (referrer есть, но не подходит под известные)
- **Other** — другие источники

### Пример URL с UTM

```text
https://example.com/?utm_source=facebook&utm_medium=social&utm_campaign=test
```

### Данные в dashboard

- **Откуда пришли посетители** — таблица источников с каналом, визитами и долей
- **UTM-кампании** — таблица кампаний с source, medium, campaign и визитами
- **Карточки**: главный источник, прямые заходы, органический поиск, соцсети

### Ограничения

- Не собирает данные из Facebook API, Google Ads API или Instagram API
- UTM-параметры берутся только из URL текущей страницы
- Полный query string текущей страницы НЕ сохраняется (privacy)
- Значения форм НЕ собираются

## AI-отчёты

AI получает: tracker analytics, цели, воронку, knowledge base, классификации, GSC данные.

```bash
curl -X POST "http://localhost:8000/api/sites/SITE_ID/reports/generate?sync=true"
curl "http://localhost:8000/api/sites/SITE_ID/reports/latest"
```

Если GSC данных нет, AI не делает выводы про SEO.

## AI Site Score

Rule-based оценка 0–100 по категориям: SEO, трафик, конверсия, структура, доверие. Если GSC не подключён — SEO получает `status=no_data` и не входит в общий score.

```bash
curl "http://localhost:8000/api/sites/SITE_ID/score?period=7d"
```

## Проверка API

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/api/sites/SITE_ID/status"
curl "http://localhost:8000/api/sites/SITE_ID/simple-analytics?days=7"
curl "http://localhost:8000/api/sites/SITE_ID/score?period=7d"
curl "http://localhost:8000/api/sites/SITE_ID/gsc/summary?period=7d"
```

## Security / Production

- Не коммитить `.env`.
- Заменить `ADMIN_DASHBOARD_PASSWORD` и `ADMIN_SESSION_SECRET`.
- В production задать `TOKEN_ENCRYPTION_KEY`.
- `ENABLE_DEMO_ENDPOINTS=false` в production.
- Ограничить `ALLOWED_ORIGINS` доменами клиентов.
- Использовать HTTPS и reverse proxy.
- In-memory rate limit — только MVP. Для production: Redis / proxy-level rate limiting.
- Google OAuth redirect URI должен совпадать с настройками Google Cloud Console.
- OAuth tokens никогда не возвращаются в API.

## Ограничения

- Нет полноценной системы пользователей/ролей.
- Нет биллинга.
- GSC sync запускается вручную (автоматический sync не реализован).
- In-memory rate limit не подходит для multi-worker production.
- Demo site содержит тестовые контакты и данные.
- Tracker не собирает значения полей форм (privacy).

## Roadmap

- Автоматический ежедневный GSC sync.
- Система пользователей и ролей.
- Redis-based rate limiting.
- Production deployment guide.
- Онбординг клиентов.
- Улучшенные AI-шаблоны отчётов.
- Экспорт отчётов в PDF.
- White-label dashboard.

## Структура проекта

```text
app/
  admin/              # HTML-админка
  api/                # REST API routes
  core/               # настройки, token crypto, логирование
  db/                 # подключение к БД
  models/             # SQLAlchemy-модели
  repositories/       # CRUD операции
  schemas/            # Pydantic-схемы
  services/           # бизнес-логика, Google client
  static/
    tracker/          # tracker.js для сайтов клиентов
    demo/             # active demo site served at /demo
  templates/          # Jinja2-шаблоны
demo-site/            # legacy demo source, not mounted by FastAPI
docs/                 # setup guide, demo scenario, production checklist
migrations/           # Alembic-миграции
```

## Полезные команды

```bash
docker compose up --build -d
docker compose exec app alembic upgrade head
docker compose logs -f app
docker compose restart app
docker compose down
python -c "import unittest; suite=unittest.defaultTestLoader.discover('tests'); result=unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(0 if result.wasSuccessful() else 1)"
python -m py_compile app/main.py
node --check app/static/tracker/tracker.js
```
