import hashlib
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import KNOWLEDGE_MAX_CHUNK_CONTENT_LENGTH, KNOWLEDGE_RAW_TEXT_CHUNK_SIZE
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.page_snapshot_repository import PageSnapshotRepository
from app.repositories.site_repository import SiteRepository
from app.schemas.knowledge_chunk import KnowledgeChunkRead

logger = logging.getLogger(__name__)


class KnowledgeService:
    MAX_CHUNK_CONTENT_LENGTH = KNOWLEDGE_MAX_CHUNK_CONTENT_LENGTH
    RAW_TEXT_CHUNK_SIZE = KNOWLEDGE_RAW_TEXT_CHUNK_SIZE

    def __init__(self, session: AsyncSession):
        self.session = session
        self.knowledge_repository = KnowledgeRepository(session)
        self.snapshot_repository = PageSnapshotRepository(session)
        self.site_repository = SiteRepository(session)

    def _compute_hash(self, site_id: uuid.UUID, path: str, chunk_type: str, content: str) -> str:
        raw = f"{site_id}:{path}:{chunk_type}:{content}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _truncate_content(self, content: str) -> str:
        if not content:
            return ""
        return content[:self.MAX_CHUNK_CONTENT_LENGTH] if len(content) > self.MAX_CHUNK_CONTENT_LENGTH else content

    def _is_useful_link(self, link: dict) -> bool:
        href = link.get("href", "")
        text = link.get("text", "")

        if not href or not text:
            return False

        if len(text.strip()) < 2:
            return False

        useful_patterns = ["wa.me", "whatsapp", "tel:", "mailto:", "phone"]
        for pattern in useful_patterns:
            if pattern in href.lower():
                return True

        if text and len(text.strip()) > 3 and not href.startswith("#") and not href.startswith("javascript:"):
            return True

        return False

    def _build_heading_chunks(self, snapshot, site_id: uuid.UUID) -> list[dict]:
        chunks = []
        headings = snapshot.headings or []

        for heading in headings:
            text = heading.get("text", "").strip()
            if not text:
                continue

            content = self._truncate_content(text)
            content_hash = self._compute_hash(site_id, snapshot.path, "heading", content)

            chunks.append({
                "site_id": site_id,
                "source_snapshot_id": snapshot.id,
                "public_site_id": snapshot.public_site_id,
                "url": snapshot.url,
                "path": snapshot.path,
                "chunk_type": "heading",
                "title": text[:200],
                "content": content,
                "content_hash": content_hash,
                "chunk_metadata": {"tag": heading.get("tag", "h1")},
            })

        return chunks

    def _build_text_block_chunks(self, snapshot, site_id: uuid.UUID) -> list[dict]:
        chunks = []
        text_blocks = snapshot.text_blocks or []

        for block in text_blocks:
            text = block.get("text", "").strip()
            if not text or len(text) < 20:
                continue

            content = self._truncate_content(text)
            title = text[:80] + "..." if len(text) > 80 else text
            content_hash = self._compute_hash(site_id, snapshot.path, "text_block", content)

            chunks.append({
                "site_id": site_id,
                "source_snapshot_id": snapshot.id,
                "public_site_id": snapshot.public_site_id,
                "url": snapshot.url,
                "path": snapshot.path,
                "chunk_type": "text_block",
                "title": title,
                "content": content,
                "content_hash": content_hash,
                "chunk_metadata": {"tag": block.get("tag", "div"), "text_length": block.get("text_length", len(text))},
            })

        return chunks

    def _build_contact_chunks(self, snapshot, site_id: uuid.UUID) -> list[dict]:
        chunks = []
        contacts = snapshot.contacts or {}

        contact_parts = []
        for email in contacts.get("emails", []):
            contact_parts.append(f"Email: {email}")
        for phone in contacts.get("phones", []):
            contact_parts.append(f"Phone: {phone}")
        for wa in contacts.get("whatsapp_links", []):
            contact_parts.append(f"WhatsApp: {wa}")
        for tel in contacts.get("tel_links", []):
            contact_parts.append(f"Tel: {tel}")
        for mailto in contacts.get("mailto_links", []):
            contact_parts.append(f"Mailto: {mailto}")

        if contact_parts:
            content = "\n".join(contact_parts)
            content = self._truncate_content(content)
            content_hash = self._compute_hash(site_id, snapshot.path, "contact", content)

            chunks.append({
                "site_id": site_id,
                "source_snapshot_id": snapshot.id,
                "public_site_id": snapshot.public_site_id,
                "url": snapshot.url,
                "path": snapshot.path,
                "chunk_type": "contact",
                "title": "Contacts",
                "content": content,
                "content_hash": content_hash,
                "chunk_metadata": contacts,
            })

        return chunks

    def _build_form_chunks(self, snapshot, site_id: uuid.UUID) -> list[dict]:
        chunks = []
        forms = snapshot.forms or []

        for i, form in enumerate(forms):
            fields = form.get("fields", [])
            if not fields:
                continue

            field_descriptions = []
            for field in fields:
                name = field.get("name", "unnamed")
                field_type = field.get("type", "text")
                placeholder = field.get("placeholder", "")
                desc = f"{name} ({field_type})"
                if placeholder:
                    desc += f" - placeholder: {placeholder}"
                field_descriptions.append(desc)

            content = f"Form {i + 1}:\n" + "\n".join(field_descriptions)
            content = self._truncate_content(content)
            content_hash = self._compute_hash(site_id, snapshot.path, "form", content)

            chunks.append({
                "site_id": site_id,
                "source_snapshot_id": snapshot.id,
                "public_site_id": snapshot.public_site_id,
                "url": snapshot.url,
                "path": snapshot.path,
                "chunk_type": "form",
                "title": f"Form {i + 1}",
                "content": content,
                "content_hash": content_hash,
                "chunk_metadata": {"action": form.get("action"), "method": form.get("method"), "field_count": len(fields)},
            })

        return chunks

    def _build_link_chunks(self, snapshot, site_id: uuid.UUID) -> list[dict]:
        chunks = []
        links = snapshot.links or []

        for link in links:
            if not self._is_useful_link(link):
                continue

            text = link.get("text", "").strip()
            href = link.get("href", "")
            content = f"{text} -> {href}"
            content = self._truncate_content(content)
            content_hash = self._compute_hash(site_id, snapshot.path, "link", content)

            chunks.append({
                "site_id": site_id,
                "source_snapshot_id": snapshot.id,
                "public_site_id": snapshot.public_site_id,
                "url": snapshot.url,
                "path": snapshot.path,
                "chunk_type": "link",
                "title": text[:200],
                "content": content,
                "content_hash": content_hash,
                "chunk_metadata": {"href": href},
            })

        return chunks

    def _build_button_chunks(self, snapshot, site_id: uuid.UUID) -> list[dict]:
        chunks = []
        buttons = snapshot.buttons or []

        for button in buttons:
            text = button.get("text", "").strip()
            if not text or len(text) < 2:
                continue

            content = self._truncate_content(text)
            content_hash = self._compute_hash(site_id, snapshot.path, "button", content)

            chunks.append({
                "site_id": site_id,
                "source_snapshot_id": snapshot.id,
                "public_site_id": snapshot.public_site_id,
                "url": snapshot.url,
                "path": snapshot.path,
                "chunk_type": "button",
                "title": "Button",
                "content": content,
                "content_hash": content_hash,
                "chunk_metadata": {"type": button.get("type", "button")},
            })

        return chunks

    def _build_raw_text_chunks(self, snapshot, site_id: uuid.UUID) -> list[dict]:
        chunks = []
        raw_text = snapshot.raw_text or ""

        if not raw_text.strip():
            return chunks

        paragraphs = raw_text.split("\n\n")
        current_chunk = ""

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            if len(current_chunk) + len(paragraph) + 2 > self.RAW_TEXT_CHUNK_SIZE:
                if current_chunk:
                    content_hash = self._compute_hash(site_id, snapshot.path, "raw_text", current_chunk)
                    chunks.append({
                        "site_id": site_id,
                        "source_snapshot_id": snapshot.id,
                        "public_site_id": snapshot.public_site_id,
                        "url": snapshot.url,
                        "path": snapshot.path,
                        "chunk_type": "raw_text",
                        "title": "Raw Text",
                        "content": current_chunk,
                        "content_hash": content_hash,
                        "chunk_metadata": {},
                    })
                current_chunk = paragraph
            else:
                current_chunk = f"{current_chunk}\n\n{paragraph}" if current_chunk else paragraph

        if current_chunk:
            content_hash = self._compute_hash(site_id, snapshot.path, "raw_text", current_chunk)
            chunks.append({
                "site_id": site_id,
                "source_snapshot_id": snapshot.id,
                "public_site_id": snapshot.public_site_id,
                "url": snapshot.url,
                "path": snapshot.path,
                "chunk_type": "raw_text",
                "title": "Raw Text",
                "content": current_chunk,
                "content_hash": content_hash,
                "chunk_metadata": {},
            })

        return chunks

    async def build_knowledge_from_snapshot(self, snapshot_id: uuid.UUID) -> list[KnowledgeChunkRead]:
        from sqlalchemy import select
        from app.models.page_snapshot import PageSnapshot

        result = await self.session.execute(select(PageSnapshot).where(PageSnapshot.id == snapshot_id))
        snapshot = result.scalar_one_or_none()

        if not snapshot:
            return []

        site = await self.site_repository.get_site_by_site_id(snapshot.public_site_id)
        if not site:
            return []

        # Пересборка страницы должна быть идемпотентной: один свежий snapshot заменяет знания того же path.
        await self.knowledge_repository.delete_chunks_by_site_path(site.id, snapshot.path)

        all_chunks = []
        all_chunks.extend(self._build_heading_chunks(snapshot, site.id))
        all_chunks.extend(self._build_text_block_chunks(snapshot, site.id))
        all_chunks.extend(self._build_contact_chunks(snapshot, site.id))
        all_chunks.extend(self._build_form_chunks(snapshot, site.id))
        all_chunks.extend(self._build_link_chunks(snapshot, site.id))
        all_chunks.extend(self._build_button_chunks(snapshot, site.id))
        all_chunks.extend(self._build_raw_text_chunks(snapshot, site.id))

        unique_chunks = []
        seen_hashes = set()
        for chunk in all_chunks:
            if chunk["content_hash"] not in seen_hashes:
                seen_hashes.add(chunk["content_hash"])
                unique_chunks.append(chunk)

        if unique_chunks:
            try:
                created_chunks = await self.knowledge_repository.create_chunks_bulk(unique_chunks)
                return [KnowledgeChunkRead.model_validate(c) for c in created_chunks]
            except Exception as e:
                logger.error(f"Failed to create knowledge chunks: {e}")
                return []

        return []

    async def build_latest_knowledge_by_site(self, public_site_id: str) -> list[KnowledgeChunkRead]:
        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return []

        # Для MVP берем самый свежий snapshot сайта; позже можно пересобирать все уникальные страницы.
        snapshots = await self.snapshot_repository.list_recent_snapshots_by_site(site.id, limit=1)
        if not snapshots:
            return []

        return await self.build_knowledge_from_snapshot(snapshots[0].id)

    async def list_chunks_by_site(self, site_id: str, limit: int = 100, offset: int = 0) -> list[KnowledgeChunkRead]:
        site = await self.site_repository.get_site_by_site_id(site_id)
        if not site:
            return []

        chunks = await self.knowledge_repository.list_chunks_by_site(site.id, limit, offset)
        return [KnowledgeChunkRead.model_validate(c) for c in chunks]
