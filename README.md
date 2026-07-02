# AI Site Analyst

AI Site Analyst - MVP-сервис для анализа сайтов клиентов через один подключаемый JavaScript-трекер.

Клиент вставляет один скрипт на сайт. Система собирает структуру страницы, события посетителей, тексты сайта как базу знаний, классифицирует блоки и формирует AI-отчеты с рекомендациями: где теряются заявки и что стоит улучшить.

## Идея

```text
Сайт клиента
-> tracker.js
-> FastAPI backend
-> PostgreSQL
-> база знаний сайта
-> AI-классификация блоков
-> AI-отчеты
-> админка
```

Главное правило проекта: AI должен опираться только на реальные тексты сайта, собранную аналитику и явно переданные данные. Если информации нет, AI должен прямо писать, что информации нет, а не придумывать цены, услуги, сроки или гарантии.

## Что готово в MVP

| Возможность | Статус |
| --- | --- |
| Клиенты и сайты | Готово |
| Генерация `site_id` | Готово |
| Подключаемый `tracker.js` | Готово |
| Сбор событий | Готово |
| Сбор структуры страницы | Готово |
| Сохранение текстов сайта как knowledge base | Готово |
| AI-классификация блоков | Готово |
| AI-отчет за период | Готово |
| Dashboard сайта в админке | Готово |
| Ручной запуск пайплайна из админки | Готово |
| Вывод найденных ссылок в browser console | Готово |
| Авторизация админки | Пока нет |
| ChromaDB / embeddings | Пока нет |
| Автоматические отчеты по расписанию | Пока нет |

## Стек

- Backend: FastAPI
- DB: PostgreSQL
- ORM: SQLAlchemy async
- Migrations: Alembic
- AI: Gemini через `google-generativeai`
- Admin frontend: Jinja2, HTML, CSS, JavaScript
- Deploy: Docker Compose

## Структура

```text
app/
  admin/              # HTML-админка
  api/                # REST API
  core/               # настройки, логирование, константы
  db/                 # подключение к БД
  models/             # SQLAlchemy-модели
  repositories/       # доступ к данным
  schemas/            # Pydantic-схемы
  services/           # бизнес-логика
  static/
    tracker/          # tracker.js для сайтов клиентов
  templates/          # Jinja2-шаблоны админки
demo-site/            # тестовый сайт для проверки трекера
migrations/           # Alembic-миграции
```

## Быстрый запуск

1. Создать `.env` из примера:

```bash
cp .env.example .env
```

На Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

2. Проверить переменные в `.env`.

Важно: перед публикацией проекта замени `GEMINI_API_KEY` в `.env.example` на безопасный placeholder. Реальный ключ должен быть только в локальном `.env` или в секретах окружения.

3. Запустить контейнеры:

```bash
docker compose up --build -d
```

4. Применить миграции:

```bash
docker compose exec app alembic upgrade head
```

5. Проверить сервис:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/health
```

Ожидаемый ответ:

```json
{"status":"ok","service":"ai-site-analyst"}
```

## Основные адреса

- Главная: http://localhost:8000
- Админка клиентов: http://localhost:8000/admin/clients
- Демо-сайт: http://localhost:8000/demo-site/
- Tracker: http://localhost:8000/static/tracker/tracker.js
- Health: http://localhost:8000/health
- API health: http://localhost:8000/api/health

При старте backend также выводит эти адреса в консоль Docker.

## Подключение tracker.js

Код для сайта клиента:

```html
<script src="http://localhost:8000/static/tracker/tracker.js" data-site-id="site_xxxxxxxxxxxx"></script>
```

Для отладки найденных ссылок можно явно включить вывод в консоль:

```html
<script src="http://localhost:8000/static/tracker/tracker.js" data-site-id="site_xxxxxxxxxxxx" data-log-links="true"></script>
```

Чтобы выключить вывод ссылок:

```html
<script src="http://localhost:8000/static/tracker/tracker.js" data-site-id="site_xxxxxxxxxxxx" data-log-links="false"></script>
```

Tracker собирает:

- pageview;
- scroll depth;
- time on page;
- page leave;
- click;
- block view;
- form submit;
- headings;
- links;
- buttons;
- forms;
- contacts;
- text blocks;
- raw text.

Значения полей форм не отправляются. Сохраняются только метаданные полей: `name`, `type`, `placeholder`.

## Проверка полного MVP-потока

1. Открыть админку:

```text
http://localhost:8000/admin/clients
```

2. Создать клиента через API:

```bash
curl -X POST http://localhost:8000/api/clients \
  -H "Content-Type: application/json" \
  -d '{"name":"НотариусOnline","email":"info@notarius-online.ru"}'
```

3. Создать сайт для клиента:

```bash
curl -X POST http://localhost:8000/api/clients/{client_id}/sites \
  -H "Content-Type: application/json" \
  -d '{
    "name": "НотариусOnline",
    "domain": "localhost",
    "allowed_domains": ["localhost", "127.0.0.1"]
  }'
```

4. Вставить полученный `site_id` в demo-site или на реальный тестовый сайт.

5. Открыть демо-сайт:

```text
http://localhost:8000/demo-site/
```

6. Сделать несколько действий на странице: скролл, клики, просмотр блоков, отправка тестовой формы.

7. Открыть страницу сайта в админке:

```text
http://localhost:8000/admin/sites/{site_id}
```

8. Нажать в админке кнопку `Полный анализ`.

Она запускает цепочку:

```text
сбор knowledge base
-> AI-классификация блоков
-> генерация AI-отчета за 7 дней
```

После выполнения на странице будут видны:

- статистика событий;
- готовность пайплайна;
- последняя воронка;
- главный вывод;
- рекомендации;
- последние snapshots;
- последние knowledge chunks;
- последние AI-классификации.

## API

Основные endpoints:

```text
GET  /health
GET  /api/health

POST /api/clients
GET  /api/clients
GET  /api/clients/{client_id}

POST /api/clients/{client_id}/sites
GET  /api/clients/{client_id}/sites
GET  /api/sites/{site_id}

POST /api/events
POST /api/page-snapshots

POST /api/sites/{site_id}/knowledge/build-latest
GET  /api/sites/{site_id}/knowledge

POST /api/sites/{site_id}/classify
GET  /api/sites/{site_id}/classifications

POST /api/sites/{site_id}/reports/generate?days=7
GET  /api/sites/{site_id}/reports
GET  /api/sites/{site_id}/reports/latest
```

## AI-режим

Если `GEMINI_API_KEY` задан, сервис использует Gemini.

Если ключ не задан, включается локальный fallback-режим:

- классификация блоков по правилам;
- отчет по собранным событиям и найденной информации;
- без выдумывания цен, услуг и фактов.

Это удобно для локальной проверки MVP без внешнего AI API.

## Правило для AI

AI должен отвечать и делать выводы только на основе:

1. текстов сайта клиента;
2. knowledge chunks;
3. классификаций блоков;
4. собранных событий аналитики;
5. явно переданных данных.

Если информации нет, AI должен писать:

```text
На сайте не найдена информация об этом.
```

Нельзя придумывать:

- цены;
- услуги;
- сроки;
- гарантии;
- факты о компании;
- причины поведения пользователей без опоры на данные.

## Ограничения MVP

- Админка пока без авторизации.
- CORS открыт глобально.
- Нет rate limiting.
- Нет полноценной tenant isolation на уровне авторизованных пользователей.
- Нет ChromaDB и embeddings.
- Нет cron-отчетов.
- Нет отдельного production-конфига.
- Нет автотестов.
- `google-generativeai` уже помечен Google как deprecated, позже стоит перейти на `google-genai`.

## Что важно перед запуском в продакшн

1. Добавить авторизацию админки.
2. Ограничить CORS доменами клиента.
3. Убрать реальные ключи из `.env.example`.
4. Добавить rate limiting для `/api/events` и `/api/page-snapshots`.
5. Добавить миграционный/seed-сценарий для первого администратора.
6. Настроить HTTPS и production domain для tracker.
7. Добавить retention policy для событий.
8. Добавить автотесты для tracker-flow, knowledge build, classification и reports.
9. Перейти с `google-generativeai` на актуальный Gemini SDK.
10. Добавить embeddings и vector search, если потребуется semantic retrieval.

## Полезные команды

```bash
docker compose ps
docker compose logs -f app
docker compose exec app alembic current
docker compose exec app alembic upgrade head
docker compose restart app
docker compose down
```

Проверка Python-файлов локально:

```bash
python -m py_compile app/main.py
```

Проверка tracker:

```bash
node --check app/static/tracker/tracker.js
```

## Текущее позиционирование

AI Site Analyst - это AI-аналитика сайта, которая сама понимает структуру сайта клиента, превращает тексты сайта в базу знаний и показывает, где теряются заявки.
