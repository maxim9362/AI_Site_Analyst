import logging

from pydantic import BaseModel, Field
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.core.rate_limit import check_rate_limit
from app.services.public_site_check_service import PublicSiteCheckError, PublicSiteCheckService


router = APIRouter(prefix="/public", tags=["public-site-check"])
logger = logging.getLogger("app.actions")


class PublicSiteCheckRequest(BaseModel):
    url: str = Field(..., min_length=3, max_length=500)


@router.post("/site-check")
async def public_site_check(payload: PublicSiteCheckRequest, request: Request):
    client_host = request.client.host if request.client else "unknown"
    logger.info("ACTION free_check_start url=%s ip=%s", payload.url, client_host)
    if not check_rate_limit(f"public-site-check:{client_host}", 8):
        logger.info("ACTION free_check_rate_limited url=%s ip=%s", payload.url, client_host)
        return JSONResponse(
            {"status": "error", "message": "Слишком много проверок. Попробуйте немного позже."},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    service = PublicSiteCheckService()
    try:
        result = await service.analyze(payload.url)
        logger.info(
            "ACTION free_check_done url=%s status=%s score=%s source=%s ip=%s",
            result.get("url", payload.url),
            result.get("status"),
            result.get("score"),
            result.get("analysis_source", "unknown"),
            client_host,
        )
        return result
    except PublicSiteCheckError as exc:
        logger.info("ACTION free_check_error url=%s error=%s ip=%s", payload.url, str(exc), client_host)
        return JSONResponse(
            {"status": "error", "message": str(exc)},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except Exception:
        logger.exception("ACTION free_check_unhandled url=%s ip=%s", payload.url, client_host)
        return JSONResponse(
            {"status": "error", "message": "Не удалось выполнить проверку сайта. Попробуйте другой URL."},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
