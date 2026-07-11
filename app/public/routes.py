from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def home_page(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@router.get("/free-check")
async def free_check_page(request: Request):
    return templates.TemplateResponse(request, "free_check.html", {})


@router.get("/site-check")
async def site_check_page(request: Request):
    return templates.TemplateResponse(request, "free_check.html", {})


@router.get("/demo")
async def demo_page(request: Request):
    return templates.TemplateResponse(request, "demo.html", {})


@router.get("/privacy")
async def privacy_page(request: Request):
    return templates.TemplateResponse(request, "privacy.html", {})


@router.get("/terms")
async def terms_page(request: Request):
    return templates.TemplateResponse(request, "terms.html", {})


@router.get("/contact")
async def contact_page(request: Request):
    return templates.TemplateResponse(request, "contact.html", {})
