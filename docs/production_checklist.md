# Production Checklist — AI Site Analyst

Чек-лист подготовки к запуску в production.

## Startup guard

- [ ] App starts without `Unsafe production settings`.
- [ ] `APP_BASE_URL` uses `https://`.
- [ ] `ADMIN_SESSION_SECRET` is not empty, default, or equal to `ADMIN_DASHBOARD_PASSWORD`.
- [ ] `TOKEN_ENCRYPTION_KEY` is set before Google OAuth is used.

## Environment

- [ ] `APP_ENV=production`
- [ ] `DEBUG=false`
- [ ] `SQL_ECHO=false`
- [ ] `.env` не коммитится в Git
- [ ] `.env.example` не содержит реальных секретов

## Security

- [ ] `ADMIN_DASHBOARD_PASSWORD` заменён на уникальный
- [ ] `ADMIN_SESSION_SECRET` заменён на уникальный
- [ ] `ADMIN_API_KEY` пустой или заменён на уникальный production key
- [ ] `ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE` задан в разумном диапазоне 1-60
- [ ] `TOKEN_ENCRYPTION_KEY` задан (Fernet key)
- [ ] `ENABLE_DEMO_ENDPOINTS=false`
- [ ] `ALLOWED_ORIGINS` ограничен доменами клиентов (не `*`)
- [ ] HTTPS настроен через reverse proxy
- [ ] Cookies работают с `secure=True`

## Database

- [ ] PostgreSQL доступен из production
- [ ] `alembic upgrade head` выполнен
- [ ] Автоматические бэкапы настроены
- [ ] Connection pool настроен для production нагрузки

## Google OAuth

- [ ] `GOOGLE_CLIENT_ID` и `GOOGLE_CLIENT_SECRET` заданы
- [ ] `GOOGLE_REDIRECT_URI` совпадает с Google Cloud Console
- [ ] OAuth scopes: `webmasters.readonly`
- [ ] Тестовый OAuth flow работает

## Infrastructure

- [ ] Reverse proxy (nginx / Caddy) настроен
- [ ] HTTPS сертификат установлен
- [ ] Rate limiting на уровне proxy
- [ ] Логи не содержат tokens или персональные данные
- [ ] Мониторинг ошибок настроен

## Application

- [ ] Технические данные скрыты от владельцев сайтов
- [ ] Demo endpoints недоступны извне
- [ ] Tracker rate limit адекватный
- [ ] CORS ограничен
