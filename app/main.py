from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.admin.routes import router as admin_router
from app.api.router import api_router
from app.api.routes.health import router as health_router
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

# TODO: Restrict CORS to allowed domains per client in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
# Демо-сайт раздается через FastAPI, чтобы tracker.js работал в обычном HTTP-контексте.
app.mount("/demo-site", StaticFiles(directory="demo-site", html=True), name="demo_site")

app.include_router(health_router)
app.include_router(api_router)
app.include_router(admin_router)
