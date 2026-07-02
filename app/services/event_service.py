import logging
import uuid
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    TRACKER_MAX_METADATA_SIZE,
    TRACKER_MAX_PATH_LENGTH,
    TRACKER_MAX_TITLE_LENGTH,
    TRACKER_MAX_URL_LENGTH,
    TRACKER_MAX_VISITOR_ID_LENGTH,
    TRACKER_MAX_SESSION_ID_LENGTH,
    VALID_EVENT_TYPES,
)
from app.repositories.event_repository import EventRepository
from app.repositories.site_repository import SiteRepository
from app.schemas.event import EventCreate, EventRead

logger = logging.getLogger(__name__)


class EventService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.event_repository = EventRepository(session)
        self.site_repository = SiteRepository(session)

    def _validate_and_sanitize(self, data: EventCreate) -> EventCreate | None:
        if not data.site_id or len(data.site_id) > 64:
            return None

        if not data.visitor_id or len(data.visitor_id) > TRACKER_MAX_VISITOR_ID_LENGTH:
            return None

        if not data.session_id or len(data.session_id) > TRACKER_MAX_SESSION_ID_LENGTH:
            return None

        if data.event_type not in VALID_EVENT_TYPES:
            return None

        if not data.url or len(data.url) > TRACKER_MAX_URL_LENGTH:
            return None

        if not data.path or len(data.path) > TRACKER_MAX_PATH_LENGTH:
            return None

        if data.title and len(data.title) > TRACKER_MAX_TITLE_LENGTH:
            data.title = data.title[:TRACKER_MAX_TITLE_LENGTH]

        if data.metadata and len(str(data.metadata)) > TRACKER_MAX_METADATA_SIZE:
            data.metadata = {}

        return data

    async def create_event(self, data: EventCreate) -> EventRead | None:
        validated = self._validate_and_sanitize(data)
        if not validated:
            return None

        site = await self.site_repository.get_site_by_site_id(validated.site_id)
        if not site:
            return None

        if not site.is_active:
            return None

        if site.allowed_domains:
            event_domain = urlparse(validated.url).hostname
            if event_domain and event_domain not in site.allowed_domains:
                return None

        event_data = {
            "site_id": site.id,
            "public_site_id": validated.site_id,
            "visitor_id": validated.visitor_id,
            "session_id": validated.session_id,
            "event_type": validated.event_type,
            "url": validated.url,
            "path": validated.path,
            "title": validated.title,
            "referrer": validated.referrer,
            "event_metadata": validated.metadata,
        }

        try:
            event = await self.event_repository.create_event(event_data)
            return EventRead.model_validate(event)
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            return None

    async def list_events_by_site(self, site_id: uuid.UUID, limit: int = 100, offset: int = 0) -> list[EventRead]:
        events = await self.event_repository.list_events_by_site(site_id, limit, offset)
        return [EventRead.model_validate(e) for e in events]

    async def count_events_by_site(self, site_id: uuid.UUID) -> int:
        return await self.event_repository.count_events_by_site(site_id)
