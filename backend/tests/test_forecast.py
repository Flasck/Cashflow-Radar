from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import grpc
import pytest
from httpx import AsyncClient

from contracts.forecast.v1 import forecast_pb2


@pytest.mark.asyncio
async def test_forecast_history_validation(client: AsyncClient, register_user):
    # Register & Create Company
    await register_user(
        client,
        {
            "full_name": "Прогнозист",
            "email": "forecaster@example.com",
            "password": "Password123!",
        },
    )
    csrf_token = client.cookies["csrf_token"]

    comp_res = await client.post(
        "/api/companies",
        json={"name": "Компания Прогноза"},
        headers={"X-CSRF-Token": csrf_token},
    )
    company_id = comp_res.json()["id"]

    # 1. Forecast on empty company -> 422 INSUFFICIENT_HISTORY
    today_str = date.today().isoformat()
    empty_res = await client.post(
        f"/api/companies/{company_id}/forecast",
        json={"history_end": today_str, "horizon_days": 30},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert empty_res.status_code == 422
    assert empty_res.json()["error"]["code"] == "INSUFFICIENT_HISTORY"

    # 2. Future history_end -> 422
    future_date = (date.today() + timedelta(days=5)).isoformat()
    future_res = await client.post(
        f"/api/companies/{company_id}/forecast",
        json={"history_end": future_date, "horizon_days": 30},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert future_res.status_code == 422

    # 3. Add single transaction only 10 days ago (total 11 days history < 30)
    tx_date = (date.today() - timedelta(days=10)).isoformat()
    await client.post(
        f"/api/companies/{company_id}/transactions",
        json={
            "operation_date": tx_date,
            "amount": "10000.00",
            "direction": "inflow",
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    short_res = await client.post(
        f"/api/companies/{company_id}/forecast",
        json={"history_end": today_str, "horizon_days": 30},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert short_res.status_code == 422
    assert short_res.json()["error"]["code"] == "INSUFFICIENT_HISTORY"
    assert "30" in short_res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_forecast_grpc_error_handling(client: AsyncClient, register_user):
    # Register & Create Company
    await register_user(
        client,
        {
            "full_name": "Прогнозист Ошибок",
            "email": "forecaster_err@example.com",
            "password": "Password123!",
        },
    )
    csrf_token = client.cookies["csrf_token"]

    comp_res = await client.post(
        "/api/companies",
        json={"name": "Компания Тестов Ошибок"},
        headers={"X-CSRF-Token": csrf_token},
    )
    company_id = comp_res.json()["id"]

    # Seed transaction 40 days ago so we have >= 30 days history
    t_start = (date.today() - timedelta(days=40)).isoformat()
    await client.post(
        f"/api/companies/{company_id}/transactions",
        json={
            "operation_date": t_start,
            "amount": "50000.00",
            "direction": "inflow",
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    today_str = date.today().isoformat()

    class FakeRpcError(grpc.aio.AioRpcError):
        def __init__(self, code, details="RPC Error"):
            self._code = code
            self._details = details

        def code(self):
            return self._code

        def details(self):
            return self._details

    # Test 503 Service Unavailable
    with patch(
        "app.forecasting.forecast_pb2_grpc.ForecastServiceStub"
    ) as mock_stub_cls:
        mock_stub = AsyncMock()
        mock_stub_cls.return_value = mock_stub
        mock_stub.Predict.side_effect = FakeRpcError(
            grpc.StatusCode.UNAVAILABLE, "Server down"
        )
        res_503 = await client.post(
            f"/api/companies/{company_id}/forecast",
            json={"history_end": today_str, "horizon_days": 30},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert res_503.status_code == 503
        assert res_503.json()["error"]["code"] == "SERVICE_UNAVAILABLE"

    # Test 504 Gateway Timeout
    with patch(
        "app.forecasting.forecast_pb2_grpc.ForecastServiceStub"
    ) as mock_stub_cls:
        mock_stub = AsyncMock()
        mock_stub_cls.return_value = mock_stub
        mock_stub.Predict.side_effect = FakeRpcError(
            grpc.StatusCode.DEADLINE_EXCEEDED, "Timeout"
        )
        res_504 = await client.post(
            f"/api/companies/{company_id}/forecast",
            json={"history_end": today_str, "horizon_days": 30},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert res_504.status_code == 504
        assert res_504.json()["error"]["code"] == "GATEWAY_TIMEOUT"

    # Test 502 Bad Gateway (malformed response point count or dates)
    with patch(
        "app.forecasting.forecast_pb2_grpc.ForecastServiceStub"
    ) as mock_stub_cls:
        mock_stub = AsyncMock()
        mock_stub_cls.return_value = mock_stub
        mock_response = forecast_pb2.PredictResponse(
            forecast=[],
            warnings=[],
            model_version="test_v1",
        )
        mock_stub.Predict.return_value = mock_response
        res_502 = await client.post(
            f"/api/companies/{company_id}/forecast",
            json={"history_end": today_str, "horizon_days": 30},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert res_502.status_code == 502
        assert res_502.json()["error"]["code"] == "BAD_GATEWAY"

    # Test 200 Successful Forecast
    with patch(
        "app.forecasting.forecast_pb2_grpc.ForecastServiceStub"
    ) as mock_stub_cls:
        mock_stub = AsyncMock()
        mock_stub_cls.return_value = mock_stub
        forecast_pts = []
        curr = date.fromisoformat(today_str) + timedelta(days=1)
        for _ in range(30):
            forecast_pts.append(
                forecast_pb2.DailyPoint(
                    date=curr.isoformat(),
                    net_cash_flow_minor=1234500,  # 12345.00
                )
            )
            curr += timedelta(days=1)

        mock_stub.Predict.return_value = forecast_pb2.PredictResponse(
            forecast=forecast_pts,
            warnings=[],
            model_version="test_v1",
        )
        res_200 = await client.post(
            f"/api/companies/{company_id}/forecast",
            json={"history_end": today_str, "horizon_days": 30},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert res_200.status_code == 200
        data_200 = res_200.json()
        assert len(data_200["forecast"]) == 30
        assert data_200["forecast"][0]["net_cash_flow"] == "12345.00"
