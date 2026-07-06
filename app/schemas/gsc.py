import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class GSCPropertyCreate(BaseModel):
    """Данные, которые админка или API передают для привязки GSC property."""

    property_url: str


class GSCPropertyRead(BaseModel):
    """Публичное представление подключенной GSC property без OAuth-секретов."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_id: uuid.UUID
    public_site_id: str
    property_url: str
    is_connected: bool
    last_sync_at: datetime | None
    google_account_email: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class GSCSearchMetricRead(BaseModel):
    """Одна строка статистики Search Console для таблиц и будущей синхронизации."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_id: uuid.UUID
    public_site_id: str
    date: date
    query: str | None
    page: str | None
    clicks: int
    impressions: int
    ctr: float
    position: float
    device: str | None
    country: str | None
    created_at: datetime
    updated_at: datetime


class GSCSummaryRead(BaseModel):
    """Короткая сводка GSC за выбранный период для dashboard и AI-контекста."""

    period: str
    is_connected: bool
    message: str | None = None
    clicks: int = 0
    impressions: int = 0
    ctr: float = 0.0
    position: float = 0.0


class GSCPropertyItem(BaseModel):
    """Одна Google Search Console property из списка доступных."""

    site_url: str
    permission_level: str | None = None


class GSCPropertiesListResponse(BaseModel):
    """Ответ endpoint получения списка GSC properties."""

    status: str
    message: str | None = None
    properties: list[GSCPropertyItem] = []


class GSCSearchAnalyticsRow(BaseModel):
    """Одна строка ответа Search Analytics API."""

    date: str | None = None
    query: str | None = None
    page: str | None = None
    device: str | None = None
    country: str | None = None
    clicks: int = 0
    impressions: int = 0
    ctr: float = 0
    position: float = 0


class GSCSearchAnalyticsTestResponse(BaseModel):
    """Ответ тестового запроса Search Analytics."""

    status: str
    message: str | None = None
    site_url: str | None = None
    period: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    dimensions: list[str] = []
    rows: list[GSCSearchAnalyticsRow] = []
