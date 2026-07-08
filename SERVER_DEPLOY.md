# Server deploy

Deployment domain: `translator-word.com`

This project is designed to run next to other Docker projects without using external port `8000` and without exposing PostgreSQL to the host.

## 1. Upload files

Upload the project through WinSCP to:

```bash
/opt/AI_Site_Analyst
```

## 2. Connect by SSH

```bash
cd /opt/AI_Site_Analyst
```

## 3. Create `.env`

```bash
cp .env.production.example .env
nano .env
```

Replace every `CHANGE_ME` value before starting the project.

## 4. Generate Fernet key

Use Python on the server:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

If `cryptography` is not installed on the server, use Docker:

```bash
docker run --rm python:3.12-slim sh -c "pip install cryptography >/dev/null && python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
```

Put the generated value into:

```env
TOKEN_ENCRYPTION_KEY=...
```

## 5. Start as a separate Compose project

```bash
docker compose -p ai_site_analyst up --build -d
```

## 6. Apply migrations

```bash
docker compose -p ai_site_analyst exec app alembic upgrade head
```

## 7. Check health

```bash
curl http://localhost:8001/health
```

Expected response:

```json
{"status":"ok","service":"ai-site-analyst"}
```

## 8. Reverse proxy

Configure the reverse proxy so the domain:

```text
translator-word.com
```

points to:

```text
127.0.0.1:8001
```

## 9. Admin panel

```text
https://translator-word.com/admin/login
```

## 10. Tracker script for client sites

```html
<script src="https://translator-word.com/static/tracker/tracker.js" data-site-id="SITE_ID"></script>
```

## Values that must be replaced in `.env`

- `POSTGRES_PASSWORD`
- password inside `DATABASE_URL`
- `ADMIN_DASHBOARD_PASSWORD`
- `ADMIN_SESSION_SECRET`
- `ADMIN_API_KEY`
- `TOKEN_ENCRYPTION_KEY`

Optional, but required for the related integrations:

- `GEMINI_API_KEY`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `PAGESPEED_API_KEY`
- `SMTP_HOST`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
