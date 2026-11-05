import grpc

from contracts import forecast_pb2

GRPC_GENERATED_VERSION = "1.85.1"
GRPC_VERSION = grpc.__version__
_version_not_supported = False

try:
    from grpc._utilities import first_version_is_lower

    _version_not_supported = first_version_is_lower(
        GRPC_VERSION, GRPC_GENERATED_VERSION
    )
except ImportError:
    _version_not_supported = True

if _version_not_supported:
    raise RuntimeError(
        f"The grpc package installed is at version {GRPC_VERSION},"
        + " but the generated code in contracts/forecast_pb2_grpc.py depends on"
        + f" grpcio>={GRPC_GENERATED_VERSION}."
        + f" Please upgrade your grpc module to grpcio>={GRPC_GENERATED_VERSION}"
        + f" or downgrade your generated code using grpcio-tools<={GRPC_VERSION}."
    )


class ForecastServiceStub:
    def __init__(self, channel):
        self.Predict = channel.unary_unary(
            "/cashflow.forecast.v1.ForecastService/Predict",
            request_serializer=forecast_pb2.PredictRequest.SerializeToString,
            response_deserializer=forecast_pb2.PredictResponse.FromString,
            _registered_method=True,
        )


class ForecastServiceServicer:
    def Predict(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")


def add_ForecastServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
        "Predict": grpc.unary_unary_rpc_method_handler(
            servicer.Predict,
            request_deserializer=forecast_pb2.PredictRequest.FromString,
            response_serializer=forecast_pb2.PredictResponse.SerializeToString,
        ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
        "cashflow.forecast.v1.ForecastService", rpc_method_handlers
    )
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers(
        "cashflow.forecast.v1.ForecastService", rpc_method_handlers
    )
