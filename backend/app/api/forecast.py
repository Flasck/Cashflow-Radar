from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_csrf, require_role
from app.db.connection import get_db
from app.forecasting import run_forecast
from app.models.membership import Membership
from app.schemas.forecast import ForecastRequest, ForecastResponse

router = APIRouter(tags=["forecast"])


@router.post("/companies/{company_id}/forecast", response_model=ForecastResponse)
async def generate_company_forecast(
    company_id: Annotated[
        int, Path(openapi_examples={"existing_company": {"value": 69}})
    ],
    payload: ForecastRequest,
    _membership: Annotated[
        Membership, Depends(require_role("owner", "treasurer", "viewer"))
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> ForecastResponse:
    return await run_forecast(
        session=session,
        company_id=company_id,
        history_end=payload.history_end,
        horizon_days=payload.horizon_days,
    )
