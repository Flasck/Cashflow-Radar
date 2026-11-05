FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY forecast_service/requirements.txt forecast_service/requirements.txt
RUN pip install --no-cache-dir -r forecast_service/requirements.txt

COPY contracts/ contracts/
COPY forecast_service/ forecast_service/

USER 10001:10001

EXPOSE 50051

CMD ["python", "-m", "forecast_service.server"]
