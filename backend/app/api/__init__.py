from fastapi import APIRouter

from app.api.account import router as account_router
from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.categories import router as categories_router
from app.api.companies import router as companies_router
from app.api.forecast import router as forecast_router
from app.api.health import router as health_router
from app.api.imports import router as imports_router
from app.api.invitations import router as invitations_router
from app.api.transactions import router as transactions_router

api_router = APIRouter(prefix="/api")

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(account_router)
api_router.include_router(companies_router)
api_router.include_router(invitations_router)
api_router.include_router(categories_router)
api_router.include_router(transactions_router)
api_router.include_router(analytics_router)
api_router.include_router(imports_router)
api_router.include_router(forecast_router)

__all__ = ["api_router"]
