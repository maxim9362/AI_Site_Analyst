from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.admin.routes import router as admin_router
from app.api.router import api_router
from app.api.routes.health import router as health_router
from app.auth.routes import router as auth_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.services.demo_page_service import render_demo_html

settings.validate_production_settings()
setup_logging()

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

# For production, set ALLOWED_ORIGINS to client domains only (e.g. "https://site1.com,https://site2.com").
allowed_origins_raw = settings.ALLOWED_ORIGINS
if allowed_origins_raw.strip() == "*":
    allowed_origins = ["*"]
else:
    allowed_origins = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
# Демо-сайт раздается через FastAPI, чтобы tracker.js работал в обычном HTTP-контексте.
app.include_router(health_router)
app.include_router(api_router)
app.include_router(auth_router)
app.include_router(admin_router)


@app.get("/demo", response_class=HTMLResponse)
async def demo_page(site_id: str | None = None):
    """Demo site for AI Site Analyst showcase."""
    resolved_site_id = site_id or settings.DEMO_SITE_ID
    try:
        html_text = render_demo_html(resolved_site_id)
    except ValueError:
        return HTMLResponse("Invalid site_id", status_code=400)

    return HTMLResponse(html_text)
