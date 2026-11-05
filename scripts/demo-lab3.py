import argparse
import getpass
import json
import os
import sys
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPCookieProcessor,
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def check_dates(dates: list[str], history_end: date, horizon: int) -> None:
    expected = [
        (history_end + timedelta(days=i)).isoformat() for i in range(1, horizon + 1)
    ]
    require(dates == expected, "Unexpected forecast length or dates")


def demo_grpc(target: str) -> None:
    import grpc

    from contracts import forecast_pb2, forecast_pb2_grpc

    start = date(2026, 7, 1)
    history = []
    for i in range(120):
        day = start + timedelta(days=i)
        sales = (
            45000 + day.weekday() * 2200 + i % 11 * 310 if day.weekday() < 5 else 9000
        )
        expenses = 17000 + i % 5 * 900
        expenses += 65000 if day.day == 1 else 0
        expenses += 110000 if day.day in (10, 25) else 0
        history.append(
            forecast_pb2.DailyPoint(
                date=day.isoformat(), net_cash_flow_minor=(sales - expenses) * 100
            )
        )
    history_end = date.fromisoformat(history[-1].date)
    expected_minor = int(
        (Decimal(sum(p.net_cash_flow_minor for p in history[-7:])) / 7).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )
    print(f"gRPC target: {target}")
    print("Method: /cashflow.forecast.v1.ForecastService/Predict")
    print(
        f"Fictional workshop: {len(history)} daily NetCF points, {start} .. {history_end}"
    )
    print("Wire amounts: signed int64 RUB kopecks; displayed amounts: RUB")
    print("History sample (not the entire request):")
    for point in history[:3]:
        print(f"  {point.date}: {Decimal(point.net_cash_flow_minor) / 100:.2f}")

    with grpc.insecure_channel(target) as channel:
        grpc.channel_ready_future(channel).result(timeout=10)
        stub = forecast_pb2_grpc.ForecastServiceStub(channel)
        for horizon in (7, 30):
            request = forecast_pb2.PredictRequest(history=history, horizon_days=horizon)
            response, call = stub.Predict.with_call(request, timeout=30)
            require(call.code() == grpc.StatusCode.OK, "Expected gRPC OK")
            require(bool(response.model_version), "Missing model version")
            check_dates([p.date for p in response.forecast], history_end, horizon)
            require(
                all(p.net_cash_flow_minor == expected_minor for p in response.forecast),
                "Expected the mean of the last seven days on every forecast day",
            )
            print(f"\nPredict(horizon_days={horizon}) -> {call.code().name}")
            print(f"model={response.model_version}, warnings={list(response.warnings)}")
            for point in response.forecast:
                print(f"  {point.date}: {Decimal(point.net_cash_flow_minor) / 100:.2f}")
            print(f"PASS: {horizon} consecutive forecast dates")

        try:
            stub.Predict(
                forecast_pb2.PredictRequest(history=history, horizon_days=14),
                timeout=10,
            )
        except grpc.RpcError as error:
            require(error.code() == grpc.StatusCode.INVALID_ARGUMENT, str(error.code()))
            print(
                f"\nPredict(horizon_days=14) -> {error.code().name}: {error.details()}"
            )
        else:
            raise RuntimeError("Invalid horizon was unexpectedly accepted")
    print("PASS: real gRPC success and server-side validation")


def demo_rest(args: argparse.Namespace) -> None:
    url = urlsplit(args.url)
    require(
        url.scheme == "http"
        and url.hostname in ("localhost", "127.0.0.1")
        and url.username is None
        and url.password is None
        and url.path in ("", "/")
        and not url.query
        and not url.fragment,
        "This demo only sends credentials to a loopback API",
    )

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise RuntimeError("API redirect refused to protect credentials")

    cookies = CookieJar()
    opener = build_opener(ProxyHandler({}), NoRedirect(), HTTPCookieProcessor(cookies))

    def request(
        path: str, payload: dict[str, object] | None = None
    ) -> tuple[int, dict]:
        headers = {"Origin": args.origin}
        if payload is not None:
            headers["Content-Type"] = "application/json"
            csrf = next((c.value for c in cookies if c.name == "csrf_token"), None)
            if csrf:
                headers["X-CSRF-Token"] = csrf
        req = Request(
            args.url.rstrip("/") + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=headers,
        )
        try:
            with opener.open(req, timeout=40) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.loads(error.read())

    password = os.environ.get("LAB3_DEMO_PASSWORD") or getpass.getpass(
        "Account password: "
    )
    status, _ = request("/api/auth/login", {"email": args.email, "password": password})
    require(status == 200, f"Login failed: HTTP {status}")
    status, company = request(f"/api/companies/{args.company_id}")
    require(status == 200, f"Company lookup failed: HTTP {status}")
    history_end = args.history_end or company.get("last_operation_date")
    require(
        bool(history_end), "Company has no operations; choose a company with >=30 days"
    )
    print(f"FastAPI: {args.url}; company={company['id']} ({company['name']})")
    print("No transactions, companies or account settings are changed.")

    for horizon in (7,) if args.expect_unavailable else (7, 30):
        path = f"/api/companies/{args.company_id}/forecast"
        payload = {"history_end": history_end, "horizon_days": horizon}
        print(f"\nPOST {path}\n{json.dumps(payload)}")
        status, response = request(path, payload)
        print(f"HTTP {status}\n{json.dumps(response, ensure_ascii=False, indent=2)}")
        if args.expect_unavailable:
            require(status == 503, "Expected HTTP 503 while Forecast Engine is stopped")
        else:
            require(status == 200, f"Forecast failed: HTTP {status}")
            require(bool(response.get("model")), "Missing model version")
            check_dates(
                [p["date"] for p in response["forecast"]],
                date.fromisoformat(str(history_end)),
                horizon,
            )
    print(
        "PASS: API reports Engine unavailable"
        if args.expect_unavailable
        else "PASS: FastAPI returned 7- and 30-day forecasts"
    )


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Demonstrate FastAPI and gRPC forecasting"
    )
    modes = parser.add_subparsers(dest="mode", required=True)
    grpc_parser = modes.add_parser("grpc", help="Call an already running gRPC Engine")
    grpc_parser.add_argument("--target", default="127.0.0.1:50052")
    rest_parser = modes.add_parser(
        "rest", help="Call FastAPI using an existing account"
    )
    rest_parser.add_argument("--url", default="http://localhost:8000")
    rest_parser.add_argument("--origin", default="http://localhost:3000")
    rest_parser.add_argument("--email", default="demo.anna@example.com")
    rest_parser.add_argument("--company-id", type=int, required=True)
    rest_parser.add_argument("--history-end", type=date.fromisoformat)
    rest_parser.add_argument("--expect-unavailable", action="store_true")
    args = parser.parse_args()
    if hasattr(args, "history_end") and args.history_end:
        args.history_end = args.history_end.isoformat()
    if args.mode == "grpc":
        demo_grpc(args.target)
    else:
        demo_rest(args)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
