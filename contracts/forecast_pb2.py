from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC, 7, 35, 1, "", "contracts/forecast.proto"
)

_sym_db = _symbol_database.Default()


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n\x18\x63ontracts/forecast.proto\x12\x14\x63\x61shflow.forecast.v1"7\n\nDailyPoint\x12\x0c\n\x04\x64\x61te\x18\x01 \x01(\t\x12\x1b\n\x13net_cash_flow_minor\x18\x02 \x01(\x03"Y\n\x0ePredictRequest\x12\x31\n\x07history\x18\x01 \x03(\x0b\x32 .cashflow.forecast.v1.DailyPoint\x12\x14\n\x0chorizon_days\x18\x02 \x01(\r"n\n\x0fPredictResponse\x12\x32\n\x08\x66orecast\x18\x01 \x03(\x0b\x32 .cashflow.forecast.v1.DailyPoint\x12\x15\n\rmodel_version\x18\x02 \x01(\t\x12\x10\n\x08warnings\x18\x03 \x03(\t2i\n\x0f\x46orecastService\x12V\n\x07Predict\x12$.cashflow.forecast.v1.PredictRequest\x1a%.cashflow.forecast.v1.PredictResponseb\x06proto3'
)

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, "contracts.forecast_pb2", _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals["_DAILYPOINT"]._serialized_start = 50
    _globals["_DAILYPOINT"]._serialized_end = 105
    _globals["_PREDICTREQUEST"]._serialized_start = 107
    _globals["_PREDICTREQUEST"]._serialized_end = 196
    _globals["_PREDICTRESPONSE"]._serialized_start = 198
    _globals["_PREDICTRESPONSE"]._serialized_end = 308
    _globals["_FORECASTSERVICE"]._serialized_start = 310
    _globals["_FORECASTSERVICE"]._serialized_end = 415
