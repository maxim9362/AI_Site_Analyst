from fastapi import APIRouter, Depends

from app.api.routes.ai_reports import router as ai_reports_router
from app.api.routes.classifications import router as classifications_router
from app.api.routes.clients import router as clients_router
from app.api.routes.events import router as events_router
from app.api.routes.gsc import public_router as gsc_public_router
from app.api.routes.gsc import router as gsc_router
from app.api.routes.health import router as health_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.page_snapshots import router as page_snapshots_router
from app.api.routes.simple_analytics import router as simple_analytics_router
from app.api.routes.site_score import router as site_score_router
from app.api.routes.site_status import router as site_status_router
from app.api.routes.sites import router as sites_router

from app.core.admin_auth import require_admin_api_access

api_router = APIRouter(prefix="/api")
private_dependencies = [Depends(require_admin_api_access)]

api_router.include_router(health_router)
api_router.include_router(events_router)
api_router.include_router(page_snapshots_router)
api_router.include_router(gsc_public_router)
api_router.include_router(clients_router, dependencies=private_dependencies)
api_router.include_router(sites_router, dependencies=private_dependencies)
api_router.include_router(knowledge_router, dependencies=private_dependencies)
api_router.include_router(classifications_router, dependencies=private_dependencies)
api_router.include_router(ai_reports_router, dependencies=private_dependencies)
api_router.include_router(site_status_router, dependencies=private_dependencies)
api_router.include_router(simple_analytics_router, dependencies=private_dependencies)
api_router.include_router(gsc_router, dependencies=private_dependencies)
api_router.include_router(site_score_router, dependencies=private_dependencies)
