import csv
import io
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal
from xml.etree.ElementTree import ParseError

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.categories import create_category, list_categories
from app.dates import get_current_moscow_date
from app.errors import (
    ConflictError,
    PayloadTooLargeError,
    UnprocessableError,
    UnsupportedMediaTypeError,
)
from app.models.transaction import Transaction
from app.schemas.common import format_decimal
from app.schemas.imports import (
    CommitRequest,
    CommitResponse,
    ImportPreviewError,
    PreviewResponse,
    PreviewRow,
    PreviewSummary,
)

MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_UNCOMPRESSED_XLSX_SIZE = 25 * 1024 * 1024
MAX_ROWS = 5000
ALLOWED_COLUMNS = {"date", "amount", "direction", "category", "purpose"}
DECIMAL_REGEX = re.compile(r"^[+-]?\d+(?:\.\d+)?$")


def parse_date_str(val: str) -> date:
    cleaned = val.strip()
    if len(cleaned) != 10 or cleaned[4] != "-" or cleaned[7] != "-":
        raise ValueError("Invalid date format")
    return date.fromisoformat(cleaned)


def parse_amount_and_direction(
    amount_str: str,
    direction_str: str | None,
    is_xlsx: bool = False,
) -> tuple[Decimal | None, str, list[str]]:
    errors: list[str] = []
    cleaned_amount = amount_str.strip()

    if not DECIMAL_REGEX.match(cleaned_amount):
        errors.append("Некорректный формат суммы")
        return None, direction_str or "", errors

    raw_dec = Decimal(cleaned_amount)

    if raw_dec == 0:
        errors.append("Сумма операции не может быть нулевой")
        return None, direction_str or "", errors

    exp = raw_dec.as_tuple().exponent
    if exp < -2:
        errors.append("Сумма не должна содержать более двух знаков после запятой")
        return None, direction_str or "", errors

    abs_dec = abs(raw_dec)
    if abs_dec > Decimal("9999999999999.99"):
        errors.append("Сумма превышает максимально допустимый предел")
        return None, direction_str or "", errors

    cleaned_dir = direction_str.strip().lower() if direction_str else None

    if cleaned_dir is not None and cleaned_dir not in ("inflow", "outflow"):
        errors.append(
            f"Недопустимое направление: '{direction_str}'. Разрешены только 'inflow' или 'outflow'"
        )
        return abs_dec, cleaned_dir, errors

    final_dir = cleaned_dir or ("outflow" if raw_dec < 0 else "inflow")
    if raw_dec < 0 and final_dir == "inflow":
        errors.append("Отрицательная сумма несовместима с направлением 'inflow'")
    if not is_xlsx and cleaned_amount.startswith("+") and final_dir == "outflow":
        errors.append("Явный знак '+' не согласуется с направлением 'outflow'")

    return abs_dec, final_dir, errors


def parse_csv_stream(content_bytes: bytes) -> list[dict]:
    try:
        text = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise UnsupportedMediaTypeError(
            "Файл CSV должен быть в кодировке UTF-8 или UTF-8 BOM"
        )

    return parse_table_rows(list(csv.reader(io.StringIO(text))))


def parse_table_rows(rows: list[list[str]], is_xlsx: bool = False) -> list[dict]:
    rows = [row for row in rows if any(cell.strip() for cell in row)]

    if not rows:
        raise UnprocessableError("Файл пуст")

    headers = [h.strip().lower() for h in rows[0]]
    while headers and not headers[-1]:
        headers.pop()
    if "" in headers:
        raise UnprocessableError("В файле есть колонка без заголовка")
    if len(headers) != len(set(headers)):
        raise UnprocessableError("Заголовки колонок содержат дубликаты")

    unknown_cols = set(headers) - ALLOWED_COLUMNS
    if unknown_cols:
        raise UnprocessableError(
            f"Неизвестные заголовки: {', '.join(sorted(unknown_cols))}"
        )

    if "date" not in headers or "amount" not in headers:
        raise UnprocessableError(
            "Файл должен содержать обязательные колонки: 'date' и 'amount'"
        )

    if len(rows) - 1 > MAX_ROWS:
        raise PayloadTooLargeError(f"Превышено максимальное число строк ({MAX_ROWS})")

    parsed_rows: list[dict] = []
    for row_idx, row in enumerate(rows[1:], start=2):
        if any(cell.strip() for cell in row[len(headers) :]):
            raise UnprocessableError(f"В строке {row_idx} есть данные без заголовка")
        row_dict = dict(zip(headers, [cell.strip() for cell in row]))
        row_dict["_row_number"] = row_idx
        row_dict["_errors"] = (
            ["Формулы в XLSX не поддерживаются"]
            if is_xlsx and any(cell.startswith("=") for cell in row)
            else []
        )
        parsed_rows.append(row_dict)

    return parsed_rows


def parse_xlsx_stream(content_bytes: bytes) -> list[dict]:
    try:
        with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
            infos = z.infolist()
            if len(infos) > 1000:
                raise PayloadTooLargeError(
                    "Количество файлов в архиве XLSX превышает допустимый лимит (максимум 1000)"
                )
            total_size = sum(info.file_size for info in infos)
            if total_size > MAX_UNCOMPRESSED_XLSX_SIZE:
                raise PayloadTooLargeError(
                    "Размер распакованного XLSX файла превышает лимит 25 МБ"
                )
    except zipfile.BadZipFile:
        raise UnsupportedMediaTypeError("Некорректный формат XLSX файла")

    try:
        wb = openpyxl.load_workbook(
            filename=io.BytesIO(content_bytes),
            read_only=True,
            data_only=False,
            keep_links=False,
        )
    except (
        InvalidFileException,
        zipfile.BadZipFile,
        KeyError,
        ValueError,
        OSError,
        ParseError,
    ):
        raise UnsupportedMediaTypeError("Не удалось прочитать XLSX файл")

    try:
        sheet = wb["transactions"] if "transactions" in wb.sheetnames else wb.active
        sheet.reset_dimensions()
        rows: list[list[str]] = []
        for row_number, row in enumerate(sheet.iter_rows(), start=1):
            if row_number > MAX_ROWS + 1:
                raise PayloadTooLargeError(
                    f"Превышено максимальное число строк ({MAX_ROWS})"
                )
            if len(row) > 10:
                raise UnprocessableError("В XLSX допускается максимум 10 колонок")
            values = []
            for cell in row:
                value = cell.value
                if isinstance(value, datetime) and value.time() == datetime.min.time():
                    value = value.date()
                values.append(str(value).strip() if value is not None else "")
            rows.append(values)
        return parse_table_rows(rows, is_xlsx=True)
    finally:
        wb.close()


async def preview_import(
    session: AsyncSession,
    company_id: int,
    filename: str,
    content_bytes: bytes,
) -> PreviewResponse:
    lower_name = filename.lower()
    is_xlsx = False
    if lower_name.endswith(".csv"):
        raw_rows = parse_csv_stream(content_bytes)
    elif lower_name.endswith(".xlsx"):
        is_xlsx = True
        raw_rows = parse_xlsx_stream(content_bytes)
    else:
        raise UnsupportedMediaTypeError("Поддерживаются только форматы CSV и XLSX")

    existing_categories = await list_categories(session, company_id)
    existing_category_names = {
        cat.name.lower(): cat.name for cat in existing_categories
    }

    preview_rows: list[PreviewRow] = []
    discovered_new_categories: dict[str, str] = {}

    valid_rows_count = 0
    error_rows_count = 0
    total_inflow = Decimal("0.00")
    total_outflow = Decimal("0.00")
    dates: list[date] = []
    today_msk = get_current_moscow_date()

    for raw in raw_rows:
        row_num = raw["_row_number"]
        row_errors: list[str] = list(raw["_errors"])

        date_val_str = raw.get("date", "")
        amount_val_str = raw.get("amount", "")
        direction_val_str = raw.get("direction", "")
        category_val = raw.get("category", "") or None
        purpose_val = raw.get("purpose", "") or None

        parsed_date: date | None = None
        if not date_val_str:
            row_errors.append("Поле 'date' обязательно для заполнения")
        else:
            try:
                parsed_date = parse_date_str(date_val_str)
                if parsed_date > today_msk:
                    row_errors.append(
                        f"Дата операции не может быть в будущем (текущая дата: {today_msk.isoformat()})"
                    )
            except ValueError:
                row_errors.append(
                    f"Некорректный формат даты '{date_val_str}'. Ожидается YYYY-MM-DD"
                )

        if not amount_val_str:
            row_errors.append("Поле 'amount' обязательно для заполнения")
            norm_amount = None
            final_direction = direction_val_str or ""
        else:
            norm_amount, final_direction, amt_errors = parse_amount_and_direction(
                amount_val_str, direction_val_str, is_xlsx=is_xlsx
            )
            row_errors.extend(amt_errors)

        if purpose_val and len(purpose_val) > 500:
            row_errors.append("Назначение платежа превышает 500 символов")

        if category_val:
            cat_clean = category_val.strip()
            if len(cat_clean) > 100:
                row_errors.append("Название категории не может превышать 100 символов")
            else:
                cat_lower = cat_clean.lower()
                if (
                    cat_lower not in existing_category_names
                    and cat_lower not in discovered_new_categories
                ):
                    discovered_new_categories[cat_lower] = cat_clean

        is_valid = len(row_errors) == 0 and norm_amount is not None
        if is_valid and parsed_date is not None and norm_amount is not None:
            valid_rows_count += 1
            dates.append(parsed_date)
            if final_direction == "inflow":
                total_inflow += norm_amount
            else:
                total_outflow += norm_amount
        else:
            error_rows_count += 1

        row_amount_display = (
            format_decimal(norm_amount) if norm_amount is not None else None
        )

        row_date_display = parsed_date.isoformat() if parsed_date else date_val_str
        row_dir_display = final_direction if is_valid else (direction_val_str or "")

        preview_rows.append(
            PreviewRow(
                row_number=row_num,
                operation_date=row_date_display,
                amount=row_amount_display,
                direction=row_dir_display,
                category=category_val,
                purpose=purpose_val,
                is_valid=is_valid,
                errors=row_errors,
            )
        )

    min_date = min(dates).isoformat() if dates else None
    max_date = max(dates).isoformat() if dates else None

    summary = PreviewSummary(
        total_rows=len(preview_rows),
        valid_rows=valid_rows_count,
        error_rows=error_rows_count,
        date_from=min_date,
        date_to=max_date,
        total_inflow=format_decimal(total_inflow),
        total_outflow=format_decimal(total_outflow),
        total_net=format_decimal(total_inflow - total_outflow),
    )

    can_commit = error_rows_count == 0 and valid_rows_count > 0
    commit_payload = (
        CommitRequest.model_validate(
            {
                "rows": [
                    row.model_dump(
                        include={
                            "operation_date",
                            "amount",
                            "direction",
                            "category",
                            "purpose",
                        }
                    )
                    for row in preview_rows
                ]
            }
        )
        if can_commit
        else None
    )

    structured_errors = [
        ImportPreviewError(row_number=row.row_number, message=message)
        for row in preview_rows
        for message in row.errors
    ]

    return PreviewResponse(
        rows=preview_rows,
        errors=structured_errors,
        new_categories=sorted(discovered_new_categories.values()),
        summary=summary,
        can_commit=can_commit,
        commit_payload=commit_payload,
    )


async def commit_import(
    session: AsyncSession,
    company_id: int,
    request: CommitRequest,
) -> CommitResponse:
    if not request.rows:
        raise UnprocessableError("Список операций для импорта пуст")

    if len(request.rows) > MAX_ROWS:
        raise PayloadTooLargeError(f"Превышено максимальное число строк ({MAX_ROWS})")

    existing_categories = await list_categories(session, company_id)
    category_map: dict[str, int] = {
        cat.name.lower(): cat.id for cat in existing_categories
    }

    new_categories_created = 0

    for row in request.rows:
        if row.category:
            cat_name = row.category.strip()
            cat_lower = cat_name.lower()
            if cat_lower not in category_map:
                try:
                    new_cat = await create_category(session, company_id, cat_name)
                    category_map[cat_lower] = new_cat.id
                    new_categories_created += 1
                except (ConflictError, IntegrityError):
                    raise ConflictError(f"Ошибка создания категории '{cat_name}'")

    tx_list: list[Transaction] = []
    for row in request.rows:
        cat_id = None
        if row.category:
            cat_id = category_map.get(row.category.strip().lower())

        tx_list.append(
            Transaction(
                company_id=company_id,
                operation_date=row.operation_date,
                amount=row.amount,
                direction=row.direction,
                category_id=cat_id,
                purpose=row.purpose,
            )
        )

    session.add_all(tx_list)
    await session.commit()

    return CommitResponse(
        imported_count=len(request.rows),
        created_categories_count=new_categories_created,
    )
