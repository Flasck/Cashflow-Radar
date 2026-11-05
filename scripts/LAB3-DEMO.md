# Защита ЛР3: FastAPI → gRPC Forecast Engine

Команды выполнять в PowerShell из `D:\Work\Cashflow-Radar`. Нужны Docker Desktop и существующая `.venv`. UI для этой демонстрации не нужен.

## 1. Контракт и отдельные процессы

```powershell
docker compose up -d --no-build --wait
docker compose ps
Get-Content contracts/forecast.proto
```

Показать отдельные контейнеры `api` и `forecast`. В контракте — unary RPC `ForecastService.Predict`: история дневного NetCF и горизонт → точки прогноза, версия модели, предупреждения. Суммы в gRPC — знаковые копейки `int64`, даты — `YYYY-MM-DD`.

## 2. Основной показ через Swagger: JWT → прогноз компании → gRPC

Открыть `http://localhost:8000/docs`.

1. В `auth` выполнить **POST /api/auth/login**: email и пароль существующего аккаунта. Например, `demo.anna@example.com`, если известен его пароль. Аккаунты и пароли не сбрасывались.
2. Из ответа скопировать `access_token`, нажать **Authorize** сверху страницы, вставить токен **без** префикса `Bearer`, подтвердить и закрыть окно.
3. В `forecast` открыть **POST /api/companies/{company_id}/forecast**, нажать **Try it out**. Пример `company_id` — `69`, существующая «Демо · Северная мануфактура». Нужен аккаунт с доступом к этой компании; пример ID не обходит проверку прав.
4. Оставить пример body `{"history_end":"2026-11-05","horizon_days":7}` и нажать **Execute**. Для второго запроса поставить `horizon_days: 30`.

Без входа — HTTP 401. Чужая компания — HTTP 404. Только входа через cookie для POST в Swagger недостаточно: выполнить **Authorize**, чтобы передавался Bearer. Публичный `/api/forecast` удалён.

Access действует 15 минут. Для обновления выполнить **POST /api/auth/refresh** с `{"refresh_token":"<текущий refresh_token>"}` из ответа login/refresh. Вернётся новая пара: заменить access в **Authorize**, сохранить новый refresh. Повторное использование старого refresh отзывает сессию; потребуется войти заново. **POST /api/auth/logout** отзывает текущую сессию и удаляет cookies. Не показывать токены и пароль на скриншотах или в логах.

Открыть логи в терминале:

```powershell
docker compose logs -f --since 1m api forecast
```

История берётся из настоящих операций выбранной компании в БД. Ожидается HTTP 200, 7/30 точек и `model: mean-7d-1.0.0`. На каждый день возвращается средний NetCF последних семи дней истории, а не фиксированный демонстрационный ответ.

В логах последовательно найти:

```text
api       | gRPC stub created: ForecastServiceStub, target=forecast:50051
api       | gRPC sending PredictRequest: history_days=90, horizon_days=7, protobuf_bytes=...
forecast  | Predict received: history_days=90, horizon_days=7
forecast  | Predict completed: forecast_points=7, model=mean-7d-1.0.0
api       | gRPC received PredictResponse: forecast_points=7, model=mean-7d-1.0.0, protobuf_bytes=...
api       | ... POST /api/companies/69/forecast HTTP/1.1 ... 200 OK
```

Docker может перемешивать вывод разных контейнеров; сопоставлять время и параметры запроса. Полные денежные данные и токены в логи не выводятся. Stub — клиентский объект внутри FastAPI, а не отдельный процесс. В отдельном процессе работает Engine.

Фраза для объяснения:

> Я вхожу в аккаунт и отправляю запрос с access JWT. FastAPI проверяет токен и доступ к компании, получает её операции из БД и собирает дневной cashflow. Переводит рубли в копейки, создаёт PredictRequest и через ForecastServiceStub вызывает Predict отдельного gRPC-сервиса. Сервис считает среднее за семь дней и возвращает PredictResponse. FastAPI переводит копейки в рубли и возвращает JSON. В логах видны отправка, обработка и получение результата.

Где показать код: `backend/app/api/forecast.py` → `predict_history` в `backend/app/forecasting.py` → `Predict` в `forecast_service/server.py` → `run_forecast` в `forecast_service/forecasting.py`. Контракт — `contracts/forecast.proto`. Для прогноза компании используется тот же gRPC-клиент.

Проверка остановки Engine — в разделе 5; можно повторить авторизованный запрос в Swagger вместо скрипта.

## 3. Прогноз существующей компании из БД

В первом терминале:

```powershell
docker compose logs -f --since 1m forecast api
```

Во втором:

```powershell
.\.venv\Scripts\python.exe scripts/demo-lab3.py rest --company-id 69
```

Ввести пароль существующего `demo.anna@example.com` (ввод скрыт). Для другого аккаунта есть `--email`, для фиксированной отсечки — `--history-end 2026-11-05`. Без отсечки берётся дата последней операции компании.

Скрипт авторизуется с cookies/CSRF и отправит два запроса:

```text
POST /api/companies/69/forecast
{"history_end": "2026-11-05", "horizon_days": 7}
```

Затем такой же запрос с горизонтом 30. На стенде компания 69 — **«Демо · Северная мануфактура»**, 90 дней вымышленных операций. Скрипт не создаёт и не меняет операции, компании или настройки аккаунта; cookies остаются только в памяти процесса.

Ожидается HTTP 200, `model: mean-7d-1.0.0`, ровно 7/30 последовательных дат после отсечки. В логах отдельного Engine одновременно появятся:

```text
Predict received: history_days=90, horizon_days=7
Predict completed: forecast_points=7, model=mean-7d-1.0.0
```

Фраза для объяснения:

> FastAPI проверяет доступ к компании, получает операции из PostgreSQL, агрегирует поступления минус выплаты по дням и формирует Protobuf-запрос. Затем через сгенерированный stub вызывает Predict по gRPC. Отдельный Engine берёт среднее за последние 7 дней, округляет до копейки и возвращает это значение на каждый день прогноза. FastAPI преобразует копейки обратно в строки рублей и отдаёт JSON клиенту. Обучения модели нет. Это прогноз чистого денежного потока, не остатка на счёте и не прибыли.

Где показать код:

- `backend/app/api/forecast.py` — REST endpoint.
- `backend/app/forecasting.py` — `PredictRequest`, `ForecastServiceStub`, `await stub.Predict(request, timeout=30.0)`.
- `forecast_service/server.py` — серверный `Predict`, расчёт и `PredictResponse`.
- `forecast_service/forecasting.py` — среднее последних 7 дней и заполнение будущих дат.
- `compose.yaml` — отдельные сервисы, адрес клиента `forecast:50051`.

## 4. Прямой gRPC и ошибка контракта

```powershell
Get-Content -Raw scripts/demo-lab3.py | docker compose exec -T api python - grpc --target forecast:50051
```

Python-клиент выполняется в контейнере API и обращается к **другому контейнеру** по сети, не через REST. Скрипт передаётся через stdin, на диск контейнера ничего не копируется. Порт Engine не опубликован на хосте; чужой Echo на `localhost:50051` не используется.

Пример — вымышленная мастерская: 120 дней продаж, расходов на материалы, аренду и зарплату, с отрицательными днями выплат. Скрипт покажет:

- `Predict(horizon_days=7) -> OK` и семь точек;
- `Predict(horizon_days=30) -> OK` и тридцать точек;
- `Predict(horizon_days=14) -> INVALID_ARGUMENT: Horizon must be 7 or 30`.

Оба успешных ответа проверяются по длине, последовательности дат, наличию версии алгоритма и совпадению со средним последних 7 дней. Это демонстрация транспорта и вычисления, **не проверка точности прогноза**.

## 5. Дополнительное доказательство для компании: без Engine прогноз не работает

Необязательно, если преподавателю достаточно запроса и логов. Остановится только Engine; PostgreSQL и API продолжат работать. `finally` восстановит Engine даже при ошибке демонстрации:

```powershell
try {
    docker compose stop forecast
    .\.venv\Scripts\python.exe scripts/demo-lab3.py rest --company-id 69 --expect-unavailable
} finally {
    docker compose start forecast
}
.\.venv\Scripts\python.exe scripts/demo-lab3.py rest --company-id 69
```

Без Engine ожидается HTTP 503 `SERVICE_UNAVAILABLE`, после запуска — снова HTTP 200. Если клиент ещё переподключается, повторить последний запрос через несколько секунд. Не использовать `down -v`: для демонстрации удаление данных не требуется.

## Проверено 05.11.2026

- Реальный Swagger: login → Authorize → компания 69 (ID заполнен автоматически) → прогноз через gRPC, HTTP 200 на горизонты 7/30. Проверка выполнена временным viewer-аккаунтом; аккаунт, membership и сессии удалены.
- UI: cookie-вход, SSR списка компаний, восстановление access через refresh при отсутствии access cookie — PASS.
- JWT: ротация, обнаружение повторного refresh, отзыв при logout/смене пароля, истечение и разделение типов токенов, Origin/CSRF и отсутствие публичного прогноза — PASS.
- Реальный прямой RPC: горизонты 7/30 — OK, горизонт 14 — INVALID_ARGUMENT.
- Реальный FastAPI → Engine: компания 69, история 08.08–05.11.2026, HTTP 200 на оба горизонта.
- При остановленном Engine — HTTP 503; после восстановления — HTTP 200 на оба горизонта.
- В логах Engine подтверждены получение истории и завершение расчёта; стенд оставлен работающим.
