from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def home_page(request: Request):
    return templates.TemplateResponse(request, "free_check.html", {})


@router.get("/free-check")
async def free_check_page(request: Request):
    return templates.TemplateResponse(request, "free_check.html", {})


@router.get("/site-check")
async def site_check_page(request: Request):
    return templates.TemplateResponse(request, "free_check.html", {})
