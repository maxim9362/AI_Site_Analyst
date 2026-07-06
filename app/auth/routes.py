import time

from fastapi import APIRouter, Depends, Form, Request, Response, status
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import check_rate_limit
from app.core.user_auth import USER_COOKIE, get_authenticated_user_id, sign_user_session
from app.db.database import get_db
from app.schemas.site import UserSiteCreate
from app.schemas.user import UserCreate
from app.services.site_service import SiteService
from app.services.user_service import UserAlreadyExistsError, UserService
from app.services.product_dashboard_service import ProductDashboardService
from app.services.pagespeed_service import PageSpeedService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _redirect(location: str) -> Response:
    return Response(status_code=302, headers={"Location": location})


def _set_user_cookie(response: Response, user_id) -> None:
    response.set_cookie(
        USER_COOKIE,
        sign_user_session(user_id, int(time.time())),
        httponly=True,
        samesite="lax",
        secure=settings.APP_ENV == "production",
        max_age=settings.ADMIN_SESSION_TTL_SECONDS,
        path="/",
    )


@router.get("/register")
async def register_page(request: Request):
    if get_authenticated_user_id(request):
        return _redirect("/sites")
    return templates.TemplateResponse(request, "register.html", {"error": None, "email": ""})


@router.post("/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    client_host = request.client.host if request.client else "unknown"
    if not check_rate_limit(f"user-register:{client_host}", settings.ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE):
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Too many attempts. Try again later.", "email": email},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    try:
        user_data = UserCreate(email=email, password=password)
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Enter a valid email and a password with at least 8 characters.", "email": email},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    service = UserService(db)
    try:
        user = await service.register_user(user_data)
    except UserAlreadyExistsError:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "User with this email already exists.", "email": email},
            status_code=status.HTTP_409_CONFLICT,
        )

    response = _redirect("/sites")
    _set_user_cookie(response, user.id)
    return response


@router.get("/login")
async def login_page(request: Request):
    if get_authenticated_user_id(request):
        return _redirect("/sites")
    return templates.TemplateResponse(request, "login.html", {"error": None, "email": ""})


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    client_host = request.client.host if request.client else "unknown"
    if not check_rate_limit(f"user-login:{client_host}", settings.ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Too many login attempts. Try again later.", "email": email},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    service = UserService(db)
    user = await service.authenticate_user(email, password)
    if not user:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid email or password.", "email": email},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    response = _redirect("/sites")
    _set_user_cookie(response, user.id)
    return response


@router.get("/logout")
async def logout():
    response = _redirect("/login")
    response.delete_cookie(USER_COOKIE, path="/")
    return response


@router.get("/sites")
async def user_sites(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = get_authenticated_user_id(request)
    if not user_id:
        return _redirect("/login")

    sites = await SiteService(db).list_sites_by_user(user_id)
    return templates.TemplateResponse(request, "user_sites.html", {"sites": sites})


@router.get("/sites/new")
async def new_site_page(request: Request):
    if not get_authenticated_user_id(request):
        return _redirect("/login")
    return templates.TemplateResponse(
        request,
        "user_site_form.html",
        {
            "error": None,
            "name": "",
            "domain": "",
            "allowed_domains": "",
            "google_client_id": "",
            "google_client_secret": "",
        },
    )


@router.post("/sites/new")
async def create_user_site(
    request: Request,
    name: str = Form(...),
    domain: str = Form(...),
    allowed_domains: str = Form(""),
    google_client_id: str = Form(...),
    google_client_secret: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user_id = get_authenticated_user_id(request)
    if not user_id:
        return _redirect("/login")

    domain_value = domain.strip()
    allowed_domain_values = [item.strip() for item in allowed_domains.splitlines() if item.strip()]
    try:
        site_data = UserSiteCreate(
            name=name.strip(),
            domain=domain_value,
            allowed_domains=allowed_domain_values or [domain_value],
            google_client_id=google_client_id.strip(),
            google_client_secret=google_client_secret.strip(),
        )
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "user_site_form.html",
            {
                "error": "Enter a site name and domain.",
                "name": name,
                "domain": domain,
                "allowed_domains": allowed_domains,
                "google_client_id": google_client_id,
                "google_client_secret": "",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    site = await SiteService(db).create_site_for_user(user_id, site_data)
    return _redirect(f"/sites/{site.site_id}/install")


@router.get("/sites/{site_id}/install")
async def site_install_code_page(site_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user_id = get_authenticated_user_id(request)
    if not user_id:
        return _redirect("/login")

    service = SiteService(db)
    site = await service.get_user_site_by_site_id(user_id, site_id)
    if not site:
        return _redirect("/sites")

    install_code = service.build_tracker_install_code(site.site_id)
    return templates.TemplateResponse(
        request,
        "user_site_install.html",
        {"site": site, "install_code": install_code},
    )


@router.get("/sites/{site_id}")
async def user_site_dashboard(
    site_id: str,
    request: Request,
    period: str = "7d",
    db: AsyncSession = Depends(get_db),
):
    user_id = get_authenticated_user_id(request)
    if not user_id:
        return _redirect("/login")

    site_service = SiteService(db)
    site = await site_service.get_user_site_by_site_id(user_id, site_id)
    if not site:
        return _redirect("/sites")

    dashboard = await ProductDashboardService(db).get_site_dashboard(site.site_id, period=period)
    if not dashboard:
        return _redirect("/sites")

    return templates.TemplateResponse(
        request,
        "user_site_dashboard.html",
        {"dashboard": dashboard, "site": dashboard["site"]},
    )


@router.post("/sites/{site_id}/pagespeed/run")
async def run_user_site_pagespeed(
    site_id: str,
    request: Request,
    strategy: str = Form("mobile"),
    db: AsyncSession = Depends(get_db),
):
    user_id = get_authenticated_user_id(request)
    if not user_id:
        return _redirect("/login")

    site = await SiteService(db).get_user_site_by_site_id(user_id, site_id)
    if not site:
        return _redirect("/sites")

    await PageSpeedService(db).run_pagespeed(site.site_id, strategy=strategy)
    return _redirect(f"/sites/{site.site_id}")
