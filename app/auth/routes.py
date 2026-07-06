import time

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request, Response, status
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import check_rate_limit
from app.core.user_auth import USER_COOKIE, get_authenticated_user_id, sign_user_session
from app.db.database import get_db
from app.schemas.site import UserSiteCreate
from app.schemas.user import UserCreate
from app.services.demo_site_bootstrap_service import create_demo_site_for_user
from app.services.site_service import SiteService
from app.services.user_service import UserAlreadyExistsError, UserService
from app.services.product_dashboard_service import ProductDashboardService
from app.services.pagespeed_service import PageSpeedService
from app.tasks.site_analysis_tasks import run_site_analysis_task

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


ANALYTICS_DETAIL_CONFIG = {
    "visitors": {
        "title": "Посетители",
        "description": "Уникальные реальные посетители и сессии за выбранный период. Боты в эти показатели не входят.",
    },
    "pageviews": {
        "title": "Просмотры",
        "description": "Просмотры страниц реальными посетителями. Здесь видно, какие страницы открывали чаще всего.",
    },
    "clicks": {
        "title": "Клики",
        "description": "Нажатия по кнопкам и ссылкам. Помогает понять, какие элементы сайта вызывают действие.",
    },
    "goals": {
        "title": "Цели",
        "description": "Целевые действия: WhatsApp, телефон, email, CTA и формы.",
    },
    "bots": {
        "title": "Боты",
        "description": "Отдельный поток технических визитов: поисковые роботы, SEO-инструменты и preview-боты.",
    },
}


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


def _build_analytics_detail(metric: str, analytics: dict) -> dict | None:
    config = ANALYTICS_DETAIL_CONFIG.get(metric)
    if not config:
        return None

    if metric == "visitors":
        visitors = analytics["visitors"]
        return {
            **config,
            "summary": [
                {"label": "Уникальные посетители", "value": visitors["unique_visitors"]},
                {"label": "Сессии", "value": visitors["unique_sessions"]},
                {"label": "Период", "value": f"{analytics['period_days']} дней"},
            ],
            "sections": [
                {
                    "title": "Что это значит",
                    "rows": [
                        {"label": "Посетитель", "value": "Один уникальный visitor_id трекера"},
                        {"label": "Сессия", "value": "Отдельный заход пользователя на сайт"},
                        {"label": "Фильтрация", "value": "Из расчета исключены события с признаком bot"},
                    ],
                }
            ],
        }

    if metric == "pageviews":
        pageviews = analytics["pageviews"]
        return {
            **config,
            "summary": [
                {"label": "Всего просмотров", "value": pageviews["total"]},
                {"label": "Страниц в топе", "value": len(pageviews["top_pages"])},
                {"label": "Период", "value": f"{analytics['period_days']} дней"},
            ],
            "sections": [
                {
                    "title": "Популярные страницы",
                    "rows": [
                        {"label": f"{page['title']} · {page['path']}", "value": page["views"]}
                        for page in pageviews["top_pages"]
                    ],
                    "empty": "Просмотров за период пока нет.",
                }
            ],
        }

    if metric == "clicks":
        clicks = analytics["clicks"]
        return {
            **config,
            "summary": [
                {"label": "Всего кликов", "value": clicks["total"]},
                {"label": "Элементов в топе", "value": len(clicks["top_clicks"])},
                {"label": "Период", "value": f"{analytics['period_days']} дней"},
            ],
            "sections": [
                {
                    "title": "Главные клики",
                    "rows": [
                        {"label": click["label"], "value": click["count"]}
                        for click in clicks["top_clicks"]
                    ],
                    "empty": "Кликов за период пока нет.",
                }
            ],
        }

    if metric == "goals":
        goals = analytics["goals"]
        funnel = analytics["funnel"]
        return {
            **config,
            "summary": [
                {"label": "Всего целей", "value": goals["total"]},
                {"label": "Контактные действия", "value": funnel["contact_actions"]},
                {"label": "Отправки форм", "value": goals["form_submits"]},
            ],
            "sections": [
                {
                    "title": "Разбивка целей",
                    "rows": [
                        {"label": "WhatsApp", "value": goals["whatsapp"]},
                        {"label": "Телефон", "value": goals["phone"]},
                        {"label": "Email", "value": goals["email"]},
                        {"label": "CTA", "value": goals["cta"]},
                        {"label": "Начали форму", "value": goals["form_starts"]},
                        {"label": "Отправили форму", "value": goals["form_submits"]},
                    ],
                },
                {
                    "title": "Воронка",
                    "rows": [
                        {"label": "Зашли на сайт", "value": funnel["site_visits"]},
                        {"label": "Смотрели услуги", "value": funnel["viewed_services"]},
                        {"label": "Смотрели цены", "value": funnel["viewed_pricing"]},
                        {"label": "Связались или нажали CTA", "value": funnel["contact_actions"]},
                    ],
                },
            ],
        }

    bots = analytics["bots"]
    return {
        **config,
        "summary": [
            {"label": "Уникальные боты", "value": bots["unique_bots"]},
            {"label": "Сессии ботов", "value": bots["unique_sessions"]},
            {"label": "События ботов", "value": bots["total_events"]},
        ],
        "sections": [
            {
                "title": "Обнаруженные боты",
                "rows": [
                    {"label": f"{bot['name']} · {bot['category']}", "value": bot["events"]}
                    for bot in bots["known_bots"]
                ],
                "empty": "Ботов за период не обнаружено.",
            },
            {
                "title": "User-Agent",
                "rows": [
                    {"label": agent["user_agent"], "value": agent["events"]}
                    for agent in bots["top_user_agents"]
                ],
                "empty": "User-Agent данных пока нет.",
            },
        ],
    }


def _score_status(score: float | None) -> str:
    if score is None:
        return "Нет данных"
    if score >= 90:
        return "Хорошо"
    if score >= 50:
        return "Нужно улучшить"
    return "Плохо"


def _build_pagespeed_detail(result) -> dict:
    score_rows = [
        {"label": "Performance", "value": result.performance_score, "status": _score_status(result.performance_score)},
        {"label": "Accessibility", "value": result.accessibility_score, "status": _score_status(result.accessibility_score)},
        {"label": "Best Practices", "value": result.best_practices_score, "status": _score_status(result.best_practices_score)},
        {"label": "SEO", "value": result.seo_score, "status": _score_status(result.seo_score)},
    ]
    metrics = [
        {
            "label": item.get("label", key),
            "value": item.get("display_value") or item.get("numeric_value") or "-",
            "status": _score_status((item.get("score") or 0) * 100 if item.get("score") is not None else None),
        }
        for key, item in (result.metrics or {}).items()
    ]
    opportunities = [
        {
            "label": item.get("title") or item.get("id") or "Рекомендация",
            "value": item.get("display_value") or f"{item.get('overall_savings_ms', 0)} ms",
            "status": _score_status((item.get("score") or 0) * 100 if item.get("score") is not None else None),
        }
        for item in (result.opportunities or [])
    ]
    diagnostics = [
        {
            "label": item.get("title") or item.get("id") or "Диагностика",
            "value": item.get("display_value") or "-",
            "status": _score_status((item.get("score") or 0) * 100 if item.get("score") is not None else None),
        }
        for item in (result.diagnostics or [])
    ]
    good = [row for row in score_rows + metrics if row["status"] == "Хорошо"]
    bad = [row for row in score_rows + metrics + opportunities + diagnostics if row["status"] in {"Плохо", "Нужно улучшить"}]

    return {
        "score_rows": score_rows,
        "metrics": metrics,
        "opportunities": opportunities,
        "diagnostics": diagnostics,
        "good": good[:8],
        "bad": bad[:8],
    }


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

    demo_site = await create_demo_site_for_user(db, user.id)
    response = _redirect(f"/sites/{demo_site.site_id}" if demo_site else "/sites")
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


@router.get("/sites/{site_id}/analytics/{metric}")
async def user_site_analytics_detail(
    site_id: str,
    metric: str,
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
    if not dashboard or not dashboard.get("tracker_analytics"):
        return _redirect(f"/sites/{site.site_id}")

    detail = _build_analytics_detail(metric, dashboard["tracker_analytics"])
    if not detail:
        return _redirect(f"/sites/{site.site_id}")

    return templates.TemplateResponse(
        request,
        "user_analytics_detail.html",
        {"dashboard": dashboard, "site": dashboard["site"], "detail": detail, "metric": metric},
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


@router.get("/sites/{site_id}/pagespeed/{strategy}")
async def user_site_pagespeed_detail(
    site_id: str,
    strategy: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user_id = get_authenticated_user_id(request)
    if not user_id:
        return _redirect("/login")

    site = await SiteService(db).get_user_site_by_site_id(user_id, site_id)
    if not site:
        return _redirect("/sites")

    pagespeed = await PageSpeedService(db).get_latest_by_site(site.site_id)
    result = pagespeed.get(strategy)
    if not result:
        return _redirect(f"/sites/{site.site_id}")

    return templates.TemplateResponse(
        request,
        "user_pagespeed_detail.html",
        {
            "site": site,
            "strategy": strategy,
            "result": result,
            "detail": _build_pagespeed_detail(result),
        },
    )


@router.post("/sites/{site_id}/analysis/run")
async def run_user_site_analysis(
    site_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    user_id = get_authenticated_user_id(request)
    if not user_id:
        return _redirect("/login")

    site = await SiteService(db).get_user_site_by_site_id(user_id, site_id)
    if not site:
        return _redirect("/sites")

    background_tasks.add_task(run_site_analysis_task, site.site_id, 7)
    return _redirect(f"/sites/{site.site_id}")
