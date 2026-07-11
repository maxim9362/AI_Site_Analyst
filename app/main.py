import logging
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.admin.routes import router as admin_router
from app.api.router import api_router
from app.api.routes.health import router as health_router
from app.auth.routes import router as auth_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.public.routes import router as public_router
from app.services.demo_page_service import render_demo_html

settings.validate_production_settings()
setup_logging()

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)
action_logger = logging.getLogger("app.actions")
templates = Jinja2Templates(directory="app/templates")

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


@app.middleware("http")
async def log_user_actions(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - start) * 1000)
    path = request.url.path
    if not path.startswith(("/static/", "/favicon.ico")):
        client_ip = request.client.host if request.client else "unknown"
        action_logger.info(
            "ACTION request %s %s -> %s %sms ip=%s",
            request.method,
            path,
            response.status_code,
            duration_ms,
            client_ip,
        )
    return response

app.mount("/static", StaticFiles(directory="app/static"), name="static")
# Демо-сайт раздается через FastAPI, чтобы tracker.js работал в обычном HTTP-контексте.
app.include_router(health_router)
app.include_router(public_router)
app.include_router(api_router)
app.include_router(auth_router)
app.include_router(admin_router)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse(request, "404.html", {}, status_code=404)


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    return templates.TemplateResponse(request, "500.html", {}, status_code=500)


@app.get("/demo", response_class=HTMLResponse)
async def demo_page(site_id: str | None = None):
    """Demo site for AI Site Analyst showcase."""
    if not settings.ENABLE_DEMO_ENDPOINTS:
        raise HTTPException(status_code=404, detail="Demo endpoints are disabled")

    resolved_site_id = site_id or settings.DEMO_SITE_ID
    try:
        html_text = render_demo_html(resolved_site_id)
    except ValueError:
        return HTMLResponse("Invalid site_id", status_code=400)

    return HTMLResponse(html_text)
