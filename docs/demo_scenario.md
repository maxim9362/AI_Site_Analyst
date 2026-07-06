# Demo Scenario — AI Site Analyst

Пошаговый сценарий для демонстрации проекта.

## Подготовка

```bash
docker compose up --build -d
docker compose exec app alembic upgrade head
```

Открыть: `http://localhost:8000/admin/login`

## Создание demo данных

```bash
# Клиент
curl -X POST http://localhost:8000/api/clients \
  -H "Content-Type: application/json" \
  -d '{"name":"НотариусOnline","email":"demo@example.com"}'

# Сайт (подставить client_id)
curl -X POST http://localhost:8000/api/clients/CLIENT_ID/sites \
  -H "Content-Type: application/json" \
  -d '{"name":"НотариусOnline","domain":"localhost","allowed_domains":["localhost"]}'

# Demo GSC данные (подставить site_id)
curl -X POST "http://localhost:8000/api/sites/SITE_ID/gsc/demo-data?days=30"

# AI report
curl -X POST "http://localhost:8000/api/sites/SITE_ID/reports/generate?sync=true"
```

## Сценарий показа (60–90 секунд)

### 1. Вступление
> AI Site Analyst — сервис, который подключается к сайту через одну строку кода и показывает владельцу бизнеса, где теряются заявки.

### 2. Подключение (10 сек)
Показать dashboard → код tracker.js → «Одна строка на сайте клиента».

### 3. Сбор данных (10 сек)
Показать Performance overview → график посещений → простая аналитика.

### 4. Цели и воронка (10 сек)
Показать: WhatsApp, телефон, email, CTA, формы → воронка: Зашли → Услуги → Заявка.

### 5. Google Search Console (10 сек)
Показать: SEO-показы, клики, CTR, позиция → таблица запросов.

### 6. AI-выводы (10 сек)
Показать: «Что происходит», «Где проблема», «Что улучшить».

### 7. Site Score (10 сек)
Показать: оценка 0–100 → разбивка по категориям → quick wins.

### 8. Demo site (10 сек)
Открыть `/demo` → нажать WhatsApp → отправить форму →вернуться на dashboard.

### 9. Вывод (5 сек)
> Система показывает: откуда трафик, где теряются заявки, что улучшить. Без технических терминов.

## Короткий вариант (30 сек)

1. Tracker.js — одна строка
2. Dashboard — трафик и цели
3. AI-вывод — что улучшить
4. Site Score — оценка сайта
