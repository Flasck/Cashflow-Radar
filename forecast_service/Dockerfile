FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    VECLIB_MAXIMUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1

COPY forecast_service/requirements.txt forecast_service/requirements.txt
RUN pip install --no-cache-dir -r forecast_service/requirements.txt

RUN groupadd --gid 10001 radar \
    && useradd --uid 10001 --gid radar --no-create-home radar

COPY contracts/ contracts/
COPY forecast_service/__init__.py forecast_service/forecasting.py forecast_service/server.py forecast_service/

USER radar

EXPOSE 50051

CMD ["python", "-m", "forecast_service.server"]
