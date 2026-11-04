import datetime
import socket
from concurrent import futures

import grpc
import pytest

from contracts.forecast.v1 import forecast_pb2, forecast_pb2_grpc
from forecast_service.forecasting import MODEL_VERSION
from forecast_service.server import ForecastServiceServicer


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def grpc_server_and_channel():
    port = find_free_port()
    bind_addr = f"127.0.0.1:{port}"

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=2),
        maximum_concurrent_rpcs=2,
    )
    forecast_pb2_grpc.add_ForecastServiceServicer_to_server(
        ForecastServiceServicer(), server
    )
    server.add_insecure_port(bind_addr)
    server.start()

    channel = grpc.insecure_channel(bind_addr)
    stub = forecast_pb2_grpc.ForecastServiceStub(channel)

    yield stub, channel, server

    channel.close()
    server.stop(grace=0)


def test_grpc_predict_success(grpc_server_and_channel):
    stub, _, _ = grpc_server_and_channel
    start_date = datetime.date(2026, 1, 1)
    points = [
        forecast_pb2.DailyPoint(
            date=(start_date + datetime.timedelta(days=i)).isoformat(),
            net_cash_flow_minor=50_000 + (i % 7) * 5_000,
        )
        for i in range(35)
    ]
    req = forecast_pb2.PredictRequest(history=points, horizon_days=7)
    resp = stub.Predict(req)

    assert resp.model_version == MODEL_VERSION
    assert len(resp.forecast) == 7
    assert "SHORT_HISTORY" in resp.warnings
    expected_first_date = (start_date + datetime.timedelta(days=35)).isoformat()
    assert resp.forecast[0].date == expected_first_date


def test_grpc_predict_invalid_history_length(grpc_server_and_channel):
    stub, _, _ = grpc_server_and_channel
    start_date = datetime.date(2026, 1, 1)
    points = [
        forecast_pb2.DailyPoint(
            date=(start_date + datetime.timedelta(days=i)).isoformat(),
            net_cash_flow_minor=10_000,
        )
        for i in range(29)
    ]
    req = forecast_pb2.PredictRequest(history=points, horizon_days=7)

    with pytest.raises(grpc.RpcError) as exc_info:
        stub.Predict(req)

    assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "History length must be between 30 and 1825" in exc_info.value.details()


def test_grpc_predict_invalid_horizon(grpc_server_and_channel):
    stub, _, _ = grpc_server_and_channel
    start_date = datetime.date(2026, 1, 1)
    points = [
        forecast_pb2.DailyPoint(
            date=(start_date + datetime.timedelta(days=i)).isoformat(),
            net_cash_flow_minor=10_000,
        )
        for i in range(30)
    ]
    req = forecast_pb2.PredictRequest(history=points, horizon_days=14)

    with pytest.raises(grpc.RpcError) as exc_info:
        stub.Predict(req)

    assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "horizon_days must be 7 or 30" in exc_info.value.details()


def test_grpc_concurrency_max2_and_recovery(grpc_server_and_channel, monkeypatch):
    import threading

    from forecast_service import server as server_mod

    stub, _, _ = grpc_server_and_channel
    start_date = datetime.date(2026, 1, 1)
    points = [
        forecast_pb2.DailyPoint(
            date=(start_date + datetime.timedelta(days=i)).isoformat(),
            net_cash_flow_minor=50_000,
        )
        for i in range(30)
    ]
    req = forecast_pb2.PredictRequest(history=points, horizon_days=7)

    rpc1_entered = threading.Event()
    rpc2_entered = threading.Event()
    unblock = threading.Event()
    entered_count = 0
    count_lock = threading.Lock()

    def blocked_run_forecast(*args, **kwargs):
        nonlocal entered_count
        with count_lock:
            entered_count += 1
            current = entered_count
        if current == 1:
            rpc1_entered.set()
        elif current == 2:
            rpc2_entered.set()
        # Wait until unblocked or timeout
        unblock.wait(timeout=5.0)
        return [("2026-01-31", 50_000) for _ in range(7)]

    monkeypatch.setattr(server_mod, "run_forecast", blocked_run_forecast)

    try:
        # Start RPC 1 and RPC 2 asynchronously
        fut1 = stub.Predict.future(req)
        assert rpc1_entered.wait(timeout=3.0)

        fut2 = stub.Predict.future(req)
        assert rpc2_entered.wait(timeout=3.0)

        # 3rd RPC should fail with RESOURCE_EXHAUSTED due to maximum_concurrent_rpcs=2
        with pytest.raises(grpc.RpcError) as exc_info:
            stub.Predict(req, timeout=1.0)
        assert exc_info.value.code() in (
            grpc.StatusCode.RESOURCE_EXHAUSTED,
            grpc.StatusCode.UNAVAILABLE,
        )

    finally:
        # Unblock running RPCs
        unblock.set()
        fut1.result()
        fut2.result()

    # Verify recovery: after unblocking, new RPC succeeds
    recovery_resp = stub.Predict(req)
    assert len(recovery_resp.forecast) == 7
