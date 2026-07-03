# AI Site Analyst - карта файлов и запросов

Этот файл помогает быстро понять, за что отвечает каждый важный файл проекта, какие блоки в нем находятся и откуда приходят HTTP-запросы.

## Общий поток

```text
Сайт клиента
-> app/static/tracker/tracker.js
-> API routes в app/api/routes/
-> services в app/services/
-> repositories в app/repositories/
-> PostgreSQL models в app/models/
-> админка в app/templates/ + app/static/js/admin.js + app/static/css/style.css
```

## Откуда приходят запросы

| Что происходит | Кто отправляет запрос | Backend-файл, который принимает запрос |
|---|---|---|
| Проверка здоровья сервиса | браузер, curl, Docker smoke test | `app/api/routes/health.py` |
| Создание клиента | curl, будущая админка | `app/api/routes/clients.py` |
| Создание сайта | curl, будущая админка | `app/api/routes/sites.py` |
| Отправка события посетителя | `app/static/tracker/tracker.js` | `app/api/routes/events.py` |
| Отправка снимка страницы | `app/static/tracker/tracker.js` | `app/api/routes/page_snapshots.py` |
| Ручная сборка базы знаний | `app/static/js/admin.js`, curl | `app/api/routes/knowledge.py` |
| Ручная AI-классификация | `app/static/js/admin.js`, curl | `app/api/routes/classifications.py` |
| Генерация AI-отчета | `app/static/js/admin.js`, curl | `app/api/routes/ai_reports.py` |
| Получение статуса сайта | админка, curl | `app/api/routes/site_status.py` |
| Получение простой аналитики | админка, curl | `app/api/routes/simple_analytics.py` |
| Открытие админских страниц | браузер | `app/admin/routes.py` |

## Корневые файлы

### `app/main.py`
Главная точка входа FastAPI.

Блоки:
- создание `FastAPI`;
- подключение CORS;
- раздача `/static`;
- раздача `/demo-site`;
- подключение API router;
- подключение admin router.

Запросы напрямую не обрабатывает, а распределяет их в `app/api/router.py`, `app/api/routes/health.py` и `app/admin/routes.py`.

### `app/api/router.py`
Главный API-router с префиксом `/api`.

Блоки:
- подключает clients;
- подключает sites;
- подключает events;
- подключает page snapshots;
- подключает knowledge;
- подключает classifications;
- подключает AI reports;
- подключает site status;
- подключает simple analytics.

Запросы приходят от `tracker.js`, `admin.js`, curl и будущей админки.

### `app/admin/routes.py`
HTML-админка.

Блоки:
- главная страница;
- список клиентов;
- страница клиента;
- страница сайта.

Данные берет из `app/services/admin_dashboard_service.py`, а HTML рендерит через шаблоны из `app/templates/`.

## API routes

### `app/api/routes/health.py`
Проверка, что сервис жив.

Endpoint:
- `GET /health`

Кто вызывает:
- браузер;
- curl;
- smoke test;
- будущий healthcheck.

### `app/api/routes/clients.py`
API клиентов.

Endpoints:
- `POST /api/clients` - создать клиента;
- `GET /api/clients` - список клиентов;
- `GET /api/clients/{client_id}` - получить клиента.

Логика уходит в `app/services/client_service.py`.

### `app/api/routes/sites.py`
API сайтов клиента.

Endpoints:
- `POST /api/clients/{client_id}/sites` - создать сайт;
- `GET /api/clients/{client_id}/sites` - список сайтов клиента;
- `GET /api/sites/{site_id}` - получить сайт по публичному `site_id`.

Логика уходит в `app/services/site_service.py`.

### `app/api/routes/events.py`
Принимает события tracker.

Endpoint:
- `POST /api/events`

Кто вызывает:
- `app/static/tracker/tracker.js`;
- curl в smoke test.

Логика уходит в `app/services/event_service.py`.

### `app/api/routes/page_snapshots.py`
Принимает снимок структуры страницы.

Endpoint:
- `POST /api/page-snapshots`

Кто вызывает:
- `app/static/tracker/tracker.js`;
- curl в smoke test.

Блоки:
- быстро сохраняет snapshot через `PageSnapshotService`;
- возвращает `accepted`;
- запускает background task `process_page_snapshot_task`.

Фоновая обработка находится в `app/tasks/page_processing_tasks.py`.

### `app/api/routes/knowledge.py`
Ручная работа с базой знаний.

Endpoints:
- `POST /api/page-snapshots/{snapshot_id}/build-knowledge`;
- `POST /api/sites/{site_id}/knowledge/build-latest`;
- `GET /api/sites/{site_id}/knowledge`.

Кто вызывает:
- `app/static/js/admin.js`;
- curl;
- разработчик из админки.

Логика уходит в `app/services/knowledge_service.py`.

### `app/api/routes/classifications.py`
AI-классификация knowledge chunks.

Endpoints:
- `POST /api/sites/{site_id}/classify`;
- `GET /api/sites/{site_id}/classifications`.

Кто вызывает:
- `app/static/js/admin.js`;
- curl;
- background task после snapshot.

Логика уходит в `app/services/classification_service.py`.

### `app/api/routes/ai_reports.py`
AI-отчеты сайта.

Endpoints:
- `POST /api/sites/{site_id}/reports/generate`;
- `POST /api/sites/{site_id}/reports/generate?sync=true`;
- `GET /api/sites/{site_id}/reports`;
- `GET /api/sites/{site_id}/reports/latest`.

Кто вызывает:
- `app/static/js/admin.js`;
- curl;
- будущая админка.

Блоки:
- обычный режим запускает `generate_ai_report_task` в фоне;
- `sync=true` ждет результат сразу;
- чтение отчетов идет через `AIReportService`.

### `app/api/routes/site_status.py`
Понятный статус обработки сайта.

Endpoint:
- `GET /api/sites/{site_id}/status`

Кто вызывает:
- админка сайта;
- curl.

Логика уходит в `app/services/site_status_service.py`.

### `app/api/routes/simple_analytics.py`
Простая аналитика для владельца сайта.

Endpoint:
- `GET /api/sites/{site_id}/simple-analytics?days=7`

Кто вызывает:
- админка сайта;
- curl.

Логика уходит в `app/services/simple_analytics_service.py`.

## Services

### `app/services/client_service.py`
Бизнес-логика клиентов.

Блоки:
- создать клиента;
- получить клиента;
- получить список клиентов.

Работает через `app/repositories/client_repository.py`.

### `app/services/site_service.py`
Бизнес-логика сайтов.

Блоки:
- создать сайт;
- сгенерировать публичный `site_id`;
- получить сайт по `site_id`;
- получить сайты клиента.

Работает через `app/repositories/site_repository.py`.

### `app/services/event_service.py`
Валидация и сохранение событий tracker.

Блоки:
- проверяет размер и тип события;
- проверяет существование сайта;
- проверяет активность сайта;
- проверяет `allowed_domains`;
- сохраняет event.

Запрос приходит из `app/api/routes/events.py`.

### `app/services/page_snapshot_service.py`
Сохранение снимка страницы.

Блоки:
- проверяет сайт;
- проверяет активность;
- сохраняет headings, links, buttons, forms, contacts, text_blocks, raw_text.

Запрос приходит из `app/api/routes/page_snapshots.py`.

### `app/services/knowledge_service.py`
Преобразует snapshot в базу знаний.

Блоки:
- heading chunks;
- text block chunks;
- contact chunks;
- form chunks;
- link chunks;
- button chunks;
- raw text chunks;
- пересборка знаний по последнему snapshot.

Вызывается из:
- `app/tasks/page_processing_tasks.py`;
- `app/api/routes/knowledge.py`.

### `app/services/classification_service.py`
Классифицирует knowledge chunks.

Блоки:
- получает chunks сайта;
- вызывает `app/services/ai_service.py`;
- сохраняет classification;
- делает rollback, если chunk изменился во время параллельной обработки.

Вызывается из:
- `app/tasks/page_processing_tasks.py`;
- `app/api/routes/classifications.py`.

### `app/services/ai_service.py`
Единый слой работы с AI.

Блоки:
- Gemini-режим, если задан ключ;
- fallback-режим без внешнего AI;
- классификация текста;
- генерация отчета.

Вызывается из:
- `classification_service.py`;
- `ai_report_service.py`.

### `app/services/analytics_service.py`
Техническая аналитика для AI-отчетов.

Блоки:
- агрегирует события;
- считает воронку для AI report;
- готовит данные для `ai_report_service.py`.

Не используется как простая бизнес-аналитика админки. Для этого есть `simple_analytics_service.py`.

### `app/services/simple_analytics_service.py`
Понятная аналитика для владельца сайта.

Блоки:
- посетители;
- просмотры страниц;
- scroll engagement;
- клики;
- цели;
- простая воронка.

Запрос приходит из `app/api/routes/simple_analytics.py`, а админка получает данные через `admin_dashboard_service.py`.

### `app/services/site_status_service.py`
Вычисляет статус обработки сайта.

Блоки:
- `no_data`;
- `collecting_data`;
- `processing`;
- `ready`;
- флаги готовности;
- даты последних данных.

Запрос приходит из `app/api/routes/site_status.py`, а админка получает данные через `admin_dashboard_service.py`.

### `app/services/ai_report_service.py`
Создает и читает AI-отчеты.

Блоки:
- собирает аналитику;
- собирает knowledge;
- вызывает AI/fallback;
- сохраняет отчет;
- возвращает latest report.

Вызывается из:
- `app/api/routes/ai_reports.py`;
- `app/tasks/report_tasks.py`.

### `app/services/admin_dashboard_service.py`
Собирает данные для HTML-админки.

Блоки:
- список клиентов со статистикой;
- страница клиента;
- страница сайта;
- status;
- simple analytics;
- latest report;
- технические таблицы.

Вызывается только из `app/admin/routes.py`.

## Tasks

### `app/tasks/page_processing_tasks.py`
Фоновая обработка snapshot.

Блоки:
- открывает новую DB session;
- строит knowledge;
- запускает classification;
- логирует ошибки, чтобы HTTP endpoint не падал.

Запускается из `app/api/routes/page_snapshots.py`.

### `app/tasks/report_tasks.py`
Фоновая генерация AI report.

Блоки:
- открывает новую DB session;
- вызывает `AIReportService`;
- логирует ошибки.

Запускается из `app/api/routes/ai_reports.py`.

## Repositories

Repositories отвечают только за SQLAlchemy-запросы к базе. Routes и templates не должны ходить в БД напрямую.

### `app/repositories/client_repository.py`
SQL-запросы для клиентов.

### `app/repositories/site_repository.py`
SQL-запросы для сайтов и поиска по публичному `site_id`.

### `app/repositories/event_repository.py`
SQL-запросы для событий tracker.

Блоки:
- создать event;
- получить события сайта;
- посчитать события;
- получить события за период;
- получить статистику для dashboard/report.

### `app/repositories/page_snapshot_repository.py`
SQL-запросы для page snapshots.

### `app/repositories/knowledge_repository.py`
SQL-запросы для knowledge chunks.

Блоки:
- создать chunks;
- найти chunks сайта;
- удалить chunks по snapshot/path;
- посчитать chunks;
- получить последнюю дату.

### `app/repositories/block_classification_repository.py`
SQL-запросы для AI-классификаций.

### `app/repositories/ai_report_repository.py`
SQL-запросы для AI-отчетов.

## Models

Models описывают таблицы PostgreSQL.

### `app/models/client.py`
Таблица клиентов.

### `app/models/site.py`
Таблица сайтов клиента.

Важные поля:
- `site_id` - публичный идентификатор для tracker;
- `allowed_domains` - список разрешенных доменов;
- `is_active` - можно ли принимать события.

### `app/models/event.py`
Таблица событий tracker.

Сюда попадают:
- pageview;
- click;
- scroll;
- block_view;
- form_submit;
- time_on_page;
- page_leave.

### `app/models/page_snapshot.py`
Таблица снимков структуры страницы.

Сюда попадают headings, links, buttons, forms, contacts, text_blocks и raw_text.

### `app/models/knowledge_chunk.py`
Таблица фрагментов базы знаний сайта.

### `app/models/block_classification.py`
Таблица AI-классификаций блоков.

### `app/models/ai_report.py`
Таблица AI-отчетов.

### `app/models/base.py`
Общие mixin-классы для UUID и timestamp-полей.

## Schemas

Schemas описывают входные и выходные JSON-структуры API.

### `app/schemas/client.py`
JSON клиента.

### `app/schemas/site.py`
JSON сайта.

### `app/schemas/event.py`
JSON события tracker.

### `app/schemas/page_snapshot.py`
JSON снимка страницы и быстрый accepted-response.

### `app/schemas/knowledge_chunk.py`
JSON knowledge chunk.

### `app/schemas/block_classification.py`
JSON AI-классификации.

### `app/schemas/ai_report.py`
JSON AI-отчета.

## Core и DB

### `app/core/config.py`
Настройки проекта из `.env`.

### `app/core/constants.py`
Константы MVP: типы событий, лимиты tracker, типы отчетов, размеры chunks.

### `app/core/logging.py`
Настройка логирования.

### `app/core/security.py`
Зарезервирован для будущей авторизации и security helpers.

### `app/db/database.py`
Создает async SQLAlchemy engine и session factory.

### `app/db/base.py`
Базовый импорт моделей для Alembic.

## Frontend админки

### `app/templates/base.html`
Базовый HTML-шаблон.

Блоки:
- подключение CSS;
- верхнее меню;
- контейнер страницы;
- подключение `app/static/js/admin.js`.

### `app/templates/index.html`
Главная HTML-страница проекта.

### `app/templates/admin_clients.html`
Список клиентов.

Данные приходят из `AdminDashboardService.get_clients_with_stats`.

### `app/templates/admin_client_detail.html`
Страница одного клиента и список его сайтов.

Данные приходят из `AdminDashboardService.get_client_detail`.

### `app/templates/admin_site_detail.html`
Главная страница сайта в админке.

Порядок блоков:
1. название сайта, домен, Site ID;
2. статус обработки;
3. код подключения tracker;
4. простая аналитика;
5. AI-вывод;
6. ручные MVP-действия;
7. технические данные.

Данные приходят из `AdminDashboardService.get_site_detail`.

### `app/static/css/style.css`
Все стили админки.

Блоки:
- общая сетка;
- кнопки;
- таблицы;
- статус сайта;
- tracker card;
- simple analytics;
- AI report card;
- technical section.

### `app/static/js/admin.js`
JS для админки.

Блоки:
- копирование embed-кода;
- запуск ручных API-действий;
- последовательный запуск endpoints для полного анализа.

Запросы из этого файла:
- `POST /api/sites/{site_id}/knowledge/build-latest`;
- `POST /api/sites/{site_id}/classify`;
- `POST /api/sites/{site_id}/reports/generate?days=7`.

## Tracker

### `app/static/tracker/tracker.js`
Скрипт, который клиент вставляет на сайт.

Блоки:
- читает `data-site-id`;
- создает visitor/session id;
- отправляет pageview;
- отправляет scroll;
- отправляет clicks;
- отправляет block views;
- отправляет time on page;
- отправляет page leave;
- собирает page snapshot.

Запросы из этого файла:
- `POST /api/events`;
- `POST /api/page-snapshots`.

## Templates и demo

### `demo-site/`
Локальный демо-сайт для проверки tracker в обычном HTTP-контексте.

Раздается через `app/main.py` по пути `/demo-site`.

## Как читать проект

Если нужно понять endpoint:

```text
app/api/routes/...
-> app/services/...
-> app/repositories/...
-> app/models/...
```

Если нужно понять админку:

```text
app/admin/routes.py
-> app/services/admin_dashboard_service.py
-> app/templates/admin_site_detail.html
-> app/static/css/style.css
-> app/static/js/admin.js
```

Если нужно понять tracker:

```text
app/static/tracker/tracker.js
-> app/api/routes/events.py
-> app/api/routes/page_snapshots.py
-> background tasks
```
