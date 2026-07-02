from fastapi import APIRouter

from app.api.routes.ai_reports import router as ai_reports_router
from app.api.routes.classifications import router as classifications_router
from app.api.routes.clients import router as clients_router
from app.api.routes.events import router as events_router
from app.api.routes.health import router as health_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.page_snapshots import router as page_snapshots_router
from app.api.routes.sites import router as sites_router

api_router = APIRouter(prefix="/api")

api_router.include_router(health_router)
api_router.include_router(clients_router)
api_router.include_router(sites_router)
api_router.include_router(events_router)
api_router.include_router(page_snapshots_router)
api_router.include_router(knowledge_router)
api_router.include_router(classifications_router)
api_router.include_router(ai_reports_router)
