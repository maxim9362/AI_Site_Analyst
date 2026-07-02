import logging
import uuid
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    SNAPSHOT_MAX_BUTTONS,
    SNAPSHOT_MAX_FORMS,
    SNAPSHOT_MAX_HEADINGS,
    SNAPSHOT_MAX_LINKS,
    SNAPSHOT_MAX_RAW_TEXT_LENGTH,
    SNAPSHOT_MAX_TEXT_BLOCK_LENGTH,
    SNAPSHOT_MAX_TEXT_BLOCKS,
    TRACKER_MAX_PATH_LENGTH,
    TRACKER_MAX_TITLE_LENGTH,
    TRACKER_MAX_URL_LENGTH,
    TRACKER_MAX_VISITOR_ID_LENGTH,
    TRACKER_MAX_SESSION_ID_LENGTH,
)
from app.repositories.page_snapshot_repository import PageSnapshotRepository
from app.repositories.site_repository import SiteRepository
from app.schemas.page_snapshot import PageSnapshotCreate, PageSnapshotRead

logger = logging.getLogger(__name__)


class PageSnapshotService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.snapshot_repository = PageSnapshotRepository(session)
        self.site_repository = SiteRepository(session)

    def _truncate_list(self, items: list, max_items: int) -> list:
        return items[:max_items] if items else []

    def _truncate_text(self, text: str, max_length: int) -> str:
        if not text:
            return ""
        return text[:max_length] if len(text) > max_length else text

    def _validate_and_sanitize(self, data: PageSnapshotCreate) -> PageSnapshotCreate | None:
        if not data.site_id or len(data.site_id) > 64:
            return None

        if not data.visitor_id or len(data.visitor_id) > TRACKER_MAX_VISITOR_ID_LENGTH:
            return None

        if not data.session_id or len(data.session_id) > TRACKER_MAX_SESSION_ID_LENGTH:
            return None

        if not data.url or len(data.url) > TRACKER_MAX_URL_LENGTH:
            return None

        if not data.path or len(data.path) > TRACKER_MAX_PATH_LENGTH:
            return None

        if data.title and len(data.title) > TRACKER_MAX_TITLE_LENGTH:
            data.title = data.title[:TRACKER_MAX_TITLE_LENGTH]

        return data

    def _limit_data(self, data: dict) -> dict:
        data["headings"] = self._truncate_list(data.get("headings", []), SNAPSHOT_MAX_HEADINGS)
        data["links"] = self._truncate_list(data.get("links", []), SNAPSHOT_MAX_LINKS)
        data["buttons"] = self._truncate_list(data.get("buttons", []), SNAPSHOT_MAX_BUTTONS)
        data["forms"] = self._truncate_list(data.get("forms", []), SNAPSHOT_MAX_FORMS)
        data["text_blocks"] = self._truncate_list(data.get("text_blocks", []), SNAPSHOT_MAX_TEXT_BLOCKS)

        for block in data.get("text_blocks", []):
            if isinstance(block, dict) and "text" in block:
                block["text"] = self._truncate_text(block["text"], SNAPSHOT_MAX_TEXT_BLOCK_LENGTH)
                block["text_length"] = len(block["text"])

        raw_text = data.get("raw_text", "")
        data["raw_text"] = self._truncate_text(raw_text, SNAPSHOT_MAX_RAW_TEXT_LENGTH)

        return data

    async def create_snapshot(self, data: PageSnapshotCreate) -> PageSnapshotRead | None:
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

        snapshot_data = {
            "site_id": site.id,
            "public_site_id": validated.site_id,
            "visitor_id": validated.visitor_id,
            "session_id": validated.session_id,
            "url": validated.url,
            "path": validated.path,
            "title": validated.title,
            "language": validated.language,
            "headings": [h.model_dump() for h in validated.headings] if validated.headings else [],
            "links": [l.model_dump() for l in validated.links] if validated.links else [],
            "buttons": [b.model_dump() for b in validated.buttons] if validated.buttons else [],
            "forms": [f.model_dump() for f in validated.forms] if validated.forms else [],
            "contacts": validated.contacts.model_dump() if validated.contacts else {},
            "text_blocks": [t.model_dump() for t in validated.text_blocks] if validated.text_blocks else [],
            "raw_text": validated.raw_text or "",
        }

        snapshot_data = self._limit_data(snapshot_data)

        try:
            snapshot = await self.snapshot_repository.create_snapshot(snapshot_data)
            return PageSnapshotRead.model_validate(snapshot)
        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            return None

    async def list_snapshots_by_site(self, site_id: uuid.UUID, limit: int = 100, offset: int = 0) -> list[PageSnapshotRead]:
        snapshots = await self.snapshot_repository.list_snapshots_by_site(site_id, limit, offset)
        return [PageSnapshotRead.model_validate(s) for s in snapshots]
