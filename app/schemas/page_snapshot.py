import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ContactInfo(BaseModel):
    emails: list[str] = []
    phones: list[str] = []
    whatsapp_links: list[str] = []
    tel_links: list[str] = []
    mailto_links: list[str] = []


class Heading(BaseModel):
    tag: str
    text: str


class Link(BaseModel):
    text: str
    href: str


class Button(BaseModel):
    text: str
    type: str


class FormField(BaseModel):
    name: str
    type: str
    placeholder: str | None = None


class Form(BaseModel):
    action: str | None = None
    method: str | None = None
    fields: list[FormField] = []


class TextBlock(BaseModel):
    tag: str
    text: str
    text_length: int


class PageSnapshotCreate(BaseModel):
    site_id: str
    visitor_id: str
    session_id: str
    url: str
    path: str
    title: str
    language: str | None = None
    headings: list[Heading] = []
    links: list[Link] = []
    buttons: list[Button] = []
    forms: list[Form] = []
    contacts: ContactInfo = ContactInfo()
    text_blocks: list[TextBlock] = []
    raw_text: str = ""


class PageSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_id: uuid.UUID
    public_site_id: str
    visitor_id: str
    session_id: str
    url: str
    path: str
    title: str
    language: str | None = None
    headings: list[dict] | None = None
    links: list[dict] | None = None
    buttons: list[dict] | None = None
    forms: list[dict] | None = None
    contacts: dict | None = None
    text_blocks: list[dict] | None = None
    raw_text: str | None = None
    created_at: datetime


class PageSnapshotAcceptedResponse(BaseModel):
    # Ответ tracker endpoint остается быстрым, а старые данные snapshot доступны во вложенном поле data.
    status: str
    message: str
    snapshot_id: uuid.UUID
    data: PageSnapshotRead
