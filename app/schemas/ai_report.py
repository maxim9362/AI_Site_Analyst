import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Recommendation(BaseModel):
    priority: str
    title: str
    reason: str
    expected_effect: str


class FunnelData(BaseModel):
    pageviews: int = 0
    viewed_services: int = 0
    viewed_pricing: int = 0
    clicked_cta: int = 0
    clicked_whatsapp: int = 0
    clicked_phone: int = 0
    submitted_form: int = 0


class AIReportCreate(BaseModel):
    site_id: uuid.UUID
    public_site_id: str
    period_start: datetime
    period_end: datetime
    report_type: str
    summary: str
    main_problem: str
    recommendations: list[Recommendation] | None = None
    funnel: FunnelData | None = None
    strengths: list[str] | None = None
    weaknesses: list[str] | None = None
    missing_information: list[str] | None = None
    raw_ai_response: dict | None = None


class AIReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_id: uuid.UUID
    public_site_id: str
    period_start: datetime
    period_end: datetime
    report_type: str
    summary: str
    main_problem: str
    recommendations: list[dict] | None = None
    funnel: dict | None = None
    strengths: list[str] | None = None
    weaknesses: list[str] | None = None
    missing_information: list[str] | None = None
    raw_ai_response: dict | None = None
    created_at: datetime
    updated_at: datetime
