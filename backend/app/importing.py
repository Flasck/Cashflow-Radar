import csv
import io
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
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

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MiB
MAX_UNCOMPRESSED_XLSX_SIZE = 25 * 1024 * 1024  # 25 MiB
MAX_ROWS = 5000
ALLOWED_COLUMNS = {"date", "amount", "direction", "category", "purpose"}
DECIMAL_REGEX = re.compile(r"^[+-]?\d+(?:\.\d+)?$")


def parse_date_str(val: str, is_xlsx: bool = False) -> date:
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

    try:
        raw_dec = Decimal(cleaned_amount)
    except (InvalidOperation, ValueError):
        errors.append("Некорректный формат суммы")
        return None, direction_str or "", errors

    if not raw_dec.is_finite():
        errors.append("Некорректный формат суммы")
        return None, direction_str or "", errors

    if raw_dec == 0:
        errors.append("Сумма операции не может быть нулевой")
        return None, direction_str or "", errors

    exp = raw_dec.as_tuple().exponent
    if not isinstance(exp, int) or exp < -2:
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

    has_plus = cleaned_amount.startswith("+")
    has_minus = cleaned_amount.startswith("-")

    if cleaned_dir is None:
        if raw_dec < 0:
            final_dir = "outflow"
        else:
            final_dir = "inflow"
    else:
        final_dir = cleaned_dir
        if is_xlsx:
            if raw_dec < 0 and final_dir == "inflow":
                errors.append(
                    "Отрицательная сумма несовместима с направлением 'inflow'"
                )
        else:
            if has_minus and final_dir == "inflow":
                errors.append("Явный знак '-' не согласуется с направлением 'inflow'")
            elif has_plus and final_dir == "outflow":
                errors.append("Явный знак '+' не согласуется с направлением 'outflow'")

    return abs_dec, final_dir, errors


def parse_csv_stream(content_bytes: bytes) -> tuple[list[dict], list[str]]:
    try:
        text = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise UnsupportedMediaTypeError(
            "Файл CSV должен быть в кодировке UTF-8 или UTF-8 BOM"
        )

    reader = csv.reader(io.StringIO(text))
    rows: list[list[str]] = [row for row in reader if any(cell.strip() for cell in row)]

    if not rows:
        raise UnprocessableError("CSV файл пуст")

    headers = [h.strip().lower() for h in rows[0]]
    if len(headers) != len(set(headers)):
        raise UnprocessableError("Заголовки колонок CSV содержат дубликаты")

    unknown_cols = set(headers) - ALLOWED_COLUMNS
    if unknown_cols:
        raise UnprocessableError(
            f"Неизвестные заголовки в CSV: {', '.join(unknown_cols)}"
        )

    if "date" not in headers or "amount" not in headers:
        raise UnprocessableError(
            "CSV должен содержать обязательные колонки: 'date' и 'amount'"
        )

    if len(rows) - 1 > MAX_ROWS:
        raise PayloadTooLargeError(f"Превышено максимальное число строк ({MAX_ROWS})")

    parsed_rows: list[dict] = []
    for row_idx, row in enumerate(rows[1:], start=2):
        row_dict = {}
        for h_idx, h in enumerate(headers):
            row_dict[h] = row[h_idx].strip() if h_idx < len(row) else ""
        row_dict["_row_number"] = row_idx
        parsed_rows.append(row_dict)

    return parsed_rows, []


def parse_xlsx_stream(content_bytes: bytes) -> tuple[list[dict], list[str]]:
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
            for info in infos:
                fn = info.filename.lower()
                if "vbaproject.bin" in fn or "externallinks" in fn:
                    raise UnprocessableError(
                        "XLSX содержит макросы или внешние связи, которые не поддерживаются"
                    )
    except zipfile.BadZipFile:
        raise UnsupportedMediaTypeError("Некорректный формат XLSX файла")

    try:
        wb = openpyxl.load_workbook(
            filename=io.BytesIO(content_bytes),
            read_only=True,
            data_only=False,
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
        sheet_name = "transactions"
        if sheet_name not in wb.sheetnames:
            sheet_name = wb.sheetnames[0]
        sheet = wb[sheet_name]
        sheet.reset_dimensions()

        row_iter = sheet.iter_rows(values_only=False)
        try:
            first_row = next(row_iter)
        except StopIteration:
            raise UnprocessableError("XLSX файл пуст")

        if len(first_row) > 10:
            raise UnprocessableError(
                "Превышено максимальное число колонок в XLSX (максимум 10)"
            )

        header_map: dict[int, str] = {}
        header_names: list[str] = []

        for c_idx, cell in enumerate(first_row):
            val = cell.value
            if cell.data_type == "f" or (
                isinstance(val, str) and val.strip().startswith("=")
            ):
                raise UnprocessableError("Формулы не поддерживаются в заголовках")

            if val is not None and str(val).strip():
                h_name = str(val).strip().lower()
                header_map[c_idx] = h_name
                header_names.append(h_name)

        if not header_names:
            raise UnprocessableError("В XLSX файле отсутствуют заголовки")

        if len(header_names) != len(set(header_names)):
            raise UnprocessableError("Заголовки колонок XLSX содержат дубликаты")

        unknown_cols = set(header_names) - ALLOWED_COLUMNS
        if unknown_cols:
            raise UnprocessableError(
                f"Неизвестные заголовки в XLSX: {', '.join(sorted(unknown_cols))}"
            )

        if "date" not in header_names or "amount" not in header_names:
            raise UnprocessableError(
                "XLSX должен содержать обязательные колонки: 'date' и 'amount'"
            )

        parsed_rows: list[dict] = []
        visited_rows = 1
        for row in row_iter:
            visited_rows += 1
            if visited_rows > MAX_ROWS + 100:
                raise PayloadTooLargeError(
                    f"Превышено максимальное число строк ({MAX_ROWS})"
                )

            if len(row) > 10:
                raise UnprocessableError(
                    f"Превышено максимальное число колонок в строке {visited_rows} (максимум 10)"
                )

            if not any(c.value is not None and str(c.value).strip() for c in row):
                continue

            row_dict: dict = {}
            formula_errors: list[str] = []

            for c_idx, cell in enumerate(row):
                val = cell.value
                has_content = val is not None and str(val).strip() != ""

                if c_idx not in header_map:
                    if has_content:
                        raise UnprocessableError(
                            f"Обнаружены данные в колонке без заголовка (колонка {c_idx + 1}, строка {visited_rows})"
                        )
                    continue

                h_name = header_map[c_idx]

                if cell.data_type == "f" or (
                    isinstance(val, str) and val.strip().startswith("=")
                ):
                    formula_errors.append(
                        f"Колонка '{h_name}' содержит формулу, формулы не поддерживаются"
                    )

                if val is None:
                    str_val = ""
                elif isinstance(val, (datetime, date)):
                    if isinstance(val, datetime) and (
                        val.hour != 0
                        or val.minute != 0
                        or val.second != 0
                        or val.microsecond != 0
                    ):
                        str_val = val.isoformat()
                    else:
                        d_val = val.date() if isinstance(val, datetime) else val
                        str_val = d_val.isoformat()
                elif isinstance(val, (int, float)):
                    if isinstance(val, float) and val.is_integer():
                        str_val = f"{int(val)}"
                    else:
                        str_val = str(val).strip()
                else:
                    str_val = str(val).strip()

                row_dict[h_name] = str_val

            for h_name in header_names:
                if h_name not in row_dict:
                    row_dict[h_name] = ""

            row_dict["_row_number"] = visited_rows
            row_dict["_formula_errors"] = formula_errors
            parsed_rows.append(row_dict)

            if len(parsed_rows) > MAX_ROWS:
                raise PayloadTooLargeError(
                    f"Превышено максимальное число строк ({MAX_ROWS})"
                )
    finally:
        wb.close()

    return parsed_rows, []


async def preview_import(
    session: AsyncSession,
    company_id: int,
    filename: str,
    content_bytes: bytes,
) -> PreviewResponse:
    if len(content_bytes) > MAX_FILE_SIZE:
        raise PayloadTooLargeError("Размер файла превышает допустимый лимит 5 МБ")

    lower_name = filename.lower()
    is_xlsx = False
    if lower_name.endswith(".csv"):
        raw_rows, _ = parse_csv_stream(content_bytes)
    elif lower_name.endswith(".xlsx"):
        is_xlsx = True
        raw_rows, _ = parse_xlsx_stream(content_bytes)
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

    for raw in raw_rows:
        row_num = raw["_row_number"]
        row_errors: list[str] = []

        date_val_str = raw.get("date", "")
        amount_val_str = raw.get("amount", "")
        direction_val_str = raw.get("direction", "")
        category_val = raw.get("category", "") or None
        purpose_val = raw.get("purpose", "") or None

        parsed_date: date | None = None
        today_msk = get_current_moscow_date()
        if not date_val_str:
            row_errors.append("Поле 'date' обязательно для заполнения")
        else:
            try:
                parsed_date = parse_date_str(date_val_str, is_xlsx=is_xlsx)
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

        if raw.get("_formula_errors"):
            row_errors.extend(raw["_formula_errors"])

        is_valid = len(row_errors) == 0 and norm_amount is not None
        if is_valid:
            valid_rows_count += 1
            assert parsed_date is not None
            dates.append(parsed_date)
            if final_direction == "inflow":
                total_inflow += norm_amount
            else:
                total_outflow += norm_amount
            row_amount_display = format_decimal(norm_amount)
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

    structured_errors: list[ImportPreviewError] = []
    for r in preview_rows:
        for err_msg in r.errors:
            structured_errors.append(
                ImportPreviewError(
                    row_number=r.row_number,
                    message=err_msg,
                )
            )

    return PreviewResponse(
        rows=preview_rows,
        errors=structured_errors,
        new_categories=sorted(discovered_new_categories.values()),
        summary=summary,
        can_commit=can_commit,
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
