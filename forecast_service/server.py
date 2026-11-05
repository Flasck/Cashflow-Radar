import logging
import os
import signal
from concurrent import futures

import grpc

from contracts import forecast_pb2, forecast_pb2_grpc
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
    def Predict(
        self,
        request: forecast_pb2.PredictRequest,
        context: grpc.ServicerContext,
    ) -> forecast_pb2.PredictResponse:
        logger.info(
            "Predict received: history_days=%d, horizon_days=%d",
            len(request.history),
            request.horizon_days,
        )

        try:
            parsed_dates, minor_values, warnings = validate_history_and_horizon(
                request.history, request.horizon_days
            )
        except ValueError as err:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(err))

        forecast_results = run_forecast(
            parsed_dates, minor_values, request.horizon_days
        )
        response = forecast_pb2.PredictResponse(
            forecast=[
                forecast_pb2.DailyPoint(date=day, net_cash_flow_minor=amount)
                for day, amount in forecast_results
            ],
            model_version=MODEL_VERSION,
            warnings=warnings,
        )
        logger.info(
            "Predict completed: forecast_points=%d, model=%s",
            len(response.forecast),
            MODEL_VERSION,
        )
        return response


def serve() -> None:
    port = os.getenv("FORECAST_PORT", "50051")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    forecast_pb2_grpc.add_ForecastServiceServicer_to_server(
        ForecastServiceServicer(), server
    )
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    logger.info("ForecastService listening on port %s", port)
    signal.signal(signal.SIGTERM, lambda *_: server.stop(grace=5))
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop(grace=5).wait()


if __name__ == "__main__":
    serve()
