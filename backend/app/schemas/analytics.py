from app.schemas.common import StrictModel


class DailyAnalyticsItem(StrictModel):
    date: str
    inflow: str
    outflow: str
    net_cash_flow: str


class DailyAnalyticsTotals(StrictModel):
    inflow: str
    outflow: str
    net_cash_flow: str


class DailyAnalyticsResponse(StrictModel):
    items: list[DailyAnalyticsItem]
    totals: DailyAnalyticsTotals


class CategoryAnalyticsItem(StrictModel):
    category_id: int | None = None
    category_name: str
    inflow: str
    outflow: str
    net_cash_flow: str


class CategoryAnalyticsResponse(StrictModel):
    items: list[CategoryAnalyticsItem]
