from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import get_db
from app.schemas.gsc import GSCPropertyCreate
from app.services.gsc_demo_service import create_demo_gsc_data
from app.services.gsc_oauth_service import GSCOAuthService
from app.services.gsc_service import GSCService

router = APIRouter(tags=["gsc"])
public_router = APIRouter(tags=["gsc"])


@router.post("/sites/{site_id}/gsc/property")
async def connect_gsc_property(
    site_id: str,
    payload: GSCPropertyCreate,
    db: AsyncSession = Depends(get_db),
):
    # Запрос из будущей страницы подключения GSC сохраняет property без OAuth-секретов.
    service = GSCService(db)
    property_obj = await service.connect_gsc_property(site_id, payload.property_url)
    if not property_obj:
        raise HTTPException(status_code=404, detail="Site not found")
    return property_obj


@router.get("/sites/{site_id}/gsc/summary")
async def get_gsc_summary(
    site_id: str,
    period: str = Query("7d"),
    db: AsyncSession = Depends(get_db),
):
    service = GSCService(db)
    summary = await service.get_gsc_summary(site_id, period)
    if summary is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return summary


@router.get("/sites/{site_id}/gsc/queries")
async def get_gsc_queries(
    site_id: str,
    period: str = Query("7d"),
    db: AsyncSession = Depends(get_db),
):
    service = GSCService(db)
    queries = await service.get_gsc_top_queries(site_id, period)
    if queries is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return {"period": period, "queries": queries}


@router.get("/sites/{site_id}/gsc/timeseries")
async def get_gsc_timeseries(
    site_id: str,
    period: str = Query("7d"),
    db: AsyncSession = Depends(get_db),
):
    service = GSCService(db)
    time_series = await service.get_gsc_time_series(site_id, period)
    if time_series is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return {"period": period, "time_series": time_series}


@router.post("/sites/{site_id}/gsc/sync")
async def sync_gsc_data(
    site_id: str,
    period: str = Query("30d"),
    db: AsyncSession = Depends(get_db),
):
    """Sync real Google Search Console data to the database."""
    service = GSCService(db)
    result = await service.sync_gsc_data(site_id, period=period)
    return result


@router.post("/sites/{site_id}/gsc/demo-data")
async def generate_demo_gsc_data(
    site_id: str,
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
):
    if not settings.ENABLE_DEMO_ENDPOINTS:
        raise HTTPException(status_code=403, detail="Demo endpoints are disabled")
    # Только для локальной разработки. В production этот endpoint нужно удалить.
    result = await create_demo_gsc_data(db, site_id, days=days)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.get("/sites/{site_id}/gsc/oauth/start")
async def start_gsc_oauth(site_id: str, db: AsyncSession = Depends(get_db)):
    """Redirect user to Google OAuth consent screen."""
    oauth_service = GSCOAuthService(db)
    auth_url = oauth_service.get_authorization_url(site_id)
    if not auth_url:
        return {
            "status": "not_configured",
            "message": "Google OAuth credentials are not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        }
    return Response(status_code=302, headers={"Location": auth_url})


@public_router.get("/gsc/oauth/callback")
async def gsc_oauth_callback(code: str = "", state: str = "", db: AsyncSession = Depends(get_db)):
    """Handle Google OAuth callback — exchange code for tokens."""
    if not code or not state:
        return {"status": "error", "message": "Missing code or state parameter"}
    oauth_service = GSCOAuthService(db)
    result = await oauth_service.handle_callback(code, state)
    if result.get("status") == "ok" and result.get("redirect_to"):
        return Response(status_code=302, headers={"Location": result["redirect_to"]})
    return result


@router.post("/sites/{site_id}/gsc/disconnect")
async def disconnect_gsc(site_id: str, db: AsyncSession = Depends(get_db)):
    """Disconnect Google Search Console by clearing tokens."""
    oauth_service = GSCOAuthService(db)
    result = await oauth_service.disconnect(site_id)
    return result


@router.get("/sites/{site_id}/gsc/properties")
async def list_gsc_properties(site_id: str, db: AsyncSession = Depends(get_db)):
    """List Google Search Console properties available to the connected account."""
    service = GSCService(db)
    result = await service.list_gsc_properties(site_id)
    return result


@router.get("/sites/{site_id}/gsc/search-analytics/test")
async def test_search_analytics(
    site_id: str,
    period: str = Query("7d"),
    dimensions: str = Query("date,query,page"),
    row_limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Test Search Analytics query against Google API. Does not save results."""
    dim_list = [d.strip() for d in dimensions.split(",") if d.strip()]
    service = GSCService(db)
    result = await service.test_search_analytics_query(
        site_id, period=period, dimensions=dim_list, row_limit=row_limit,
    )
    return result
