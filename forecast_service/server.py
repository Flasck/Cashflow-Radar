"""gRPC server for Forecast Engine in CashFlow Radar."""

import logging
import os
import signal
import threading
from concurrent import futures

import grpc

from contracts.forecast.v1 import forecast_pb2, forecast_pb2_grpc
from forecast_service.forecasting import (
    MODEL_VERSION,
    run_forecast,
    validate_history_and_horizon,
)

logger = logging.getLogger("forecast_service")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


class ForecastServiceServicer(forecast_pb2_grpc.ForecastServiceServicer):
    """Servicer handling Predict requests."""

    def Predict(
        self,
        request: forecast_pb2.PredictRequest,
        context: grpc.ServicerContext,
    ) -> forecast_pb2.PredictResponse:
        """Handle forecast calculation with cancellation support and strict validation."""
        if not context.is_active():
            context.abort(
                grpc.StatusCode.CANCELLED,
                "Request was cancelled before processing started",
            )

        try:
            parsed_dates, minor_values, warnings = validate_history_and_horizon(
                request.history, request.horizon_days
            )
        except ValueError as err:
            logger.info("Validation rejected Predict request: %s", err)
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(err))

        # Convert minor units (kopecks) to float rubles for model fitting
        history_rubles = [v / 100.0 for v in minor_values]

        def check_active() -> bool:
            return context.is_active()

        try:
            forecast_results = run_forecast(
                history_dates=parsed_dates,
                history_rubles=history_rubles,
                horizon_days=request.horizon_days,
                is_active_cb=check_active,
            )
        except RuntimeError as err:
            logger.warning("Predict request cancelled by client: %s", err)
            context.abort(grpc.StatusCode.CANCELLED, str(err))
        except Exception as err:
            logger.exception("Unexpected error during forecasting")
            context.abort(
                grpc.StatusCode.INTERNAL, f"Internal forecasting error: {err!s}"
            )

        response_points = [
            forecast_pb2.DailyPoint(date=d, net_cash_flow_minor=val)
            for d, val in forecast_results
        ]

        return forecast_pb2.PredictResponse(
            forecast=response_points,
            model_version=MODEL_VERSION,
            warnings=warnings,
        )


def create_grpc_server(bind_address: str | None = None) -> grpc.Server:
    """Create configured gRPC server with max 2 workers and maximum_concurrent_rpcs=2."""
    if not bind_address:
        port = os.getenv("FORECAST_PORT") or os.getenv("FORECAST_GRPC_PORT", "50051")
        host = os.getenv("FORECAST_GRPC_HOST", "0.0.0.0")
        bind_address = f"{host}:{port}"

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=2),
        maximum_concurrent_rpcs=2,
    )
    forecast_pb2_grpc.add_ForecastServiceServicer_to_server(
        ForecastServiceServicer(), server
    )
    server.add_insecure_port(bind_address)
    logger.info(
        "Configured ForecastService gRPC server on %s (max_concurrent_rpcs=2)",
        bind_address,
    )
    return server


def serve(bind_address: str | None = None) -> None:
    """Run gRPC server with graceful stop handling."""
    server = create_grpc_server(bind_address)
    server.start()

    stop_event = threading.Event()

    def handle_signal(sig, frame):
        logger.info("Received termination signal %s, initiating graceful stop...", sig)
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Wait for termination with timed wait loop to handle Windows SIGINT / Ctrl+C cleanly
    try:
        while not stop_event.is_set():
            stop_event.wait(timeout=0.5)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, stopping...")
        stop_event.set()

    logger.info("Stopping gRPC server with 5s grace period...")
    server.stop(grace=5).wait()
    logger.info("gRPC server stopped cleanly.")


if __name__ == "__main__":
    serve()
