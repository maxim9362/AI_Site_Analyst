import time
import uuid

from fastapi import APIRouter, Depends, Form, Request, Response, status
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_auth import ADMIN_COOKIE, is_admin_authenticated, sign_admin_session, verify_admin_password
from app.core.config import settings
from app.core.rate_limit import check_rate_limit
from app.core.user_auth import get_authenticated_user_id
from app.db.database import get_db
from app.services.admin_dashboard_service import AdminDashboardService
from app.services.product_dashboard_service import ProductDashboardService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/admin/login")
async def admin_login_page(request: Request):
    if is_admin_authenticated(request):
        return Response(status_code=302, headers={"Location": "/admin/clients"})
    return templates.TemplateResponse(request, "admin_login.html", {"error": None})


@router.post("/admin/login")
async def admin_login_submit(request: Request, password: str = Form(...)):
    client_host = request.client.host if request.client else "unknown"
    if not check_rate_limit(f"admin-login:{client_host}", settings.ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE):
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {"error": "Too many login attempts. Try again later."},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    if not verify_admin_password(password):
        return templates.TemplateResponse(request, "admin_login.html", {"error": "Неверный пароль"})

    signed_value = sign_admin_session(int(time.time()))
    response = Response(status_code=302, headers={"Location": "/admin/clients"})
    response.set_cookie(
        ADMIN_COOKIE,
        signed_value,
        httponly=True,
        samesite="lax",
        secure=settings.APP_ENV == "production",
        max_age=settings.ADMIN_SESSION_TTL_SECONDS,
        path="/",
    )
    return response


@router.get("/admin/logout")
async def admin_logout():
    response = Response(status_code=302, headers={"Location": "/admin/login"})
    response.delete_cookie(ADMIN_COOKIE)
    return response


@router.get("/")
async def index(request: Request):
    if get_authenticated_user_id(request):
        return Response(status_code=302, headers={"Location": "/sites"})
    return Response(status_code=302, headers={"Location": "/login"})


@router.get("/admin/clients")
async def admin_clients(request: Request, db: AsyncSession = Depends(get_db)):
    if not is_admin_authenticated(request):
        return Response(status_code=302, headers={"Location": "/admin/login"})
    service = AdminDashboardService(db)
    clients_data = await service.get_clients_with_stats()
    return templates.TemplateResponse(request, "admin_clients.html", {
        "clients_data": clients_data,
    })


@router.get("/admin/clients/{client_id}")
async def admin_client_detail(request: Request, client_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    if not is_admin_authenticated(request):
        return Response(status_code=302, headers={"Location": "/admin/login"})
    service = AdminDashboardService(db)
    data = await service.get_client_detail(client_id)
    if not data:
        return templates.TemplateResponse(request, "index.html", {
            "error": "Client not found",
        })
    return templates.TemplateResponse(request, "admin_client_detail.html", {
        "client": data["client"],
        "sites": data["sites"],
    })


@router.get("/admin/sites/{site_id}")
async def admin_site_detail(
    request: Request,
    site_id: str,
    period: str = "7d",
    db: AsyncSession = Depends(get_db),
):
    if not is_admin_authenticated(request):
        return Response(status_code=302, headers={"Location": "/admin/login"})
    service = ProductDashboardService(db)
    dashboard = await service.get_site_dashboard(site_id, period=period)
    if not dashboard:
        return templates.TemplateResponse(request, "index.html", {
            "error": "Site not found",
        })
    return templates.TemplateResponse(request, "admin_site_detail.html", {
        "dashboard": dashboard,
        "site": dashboard["site"],
    })
