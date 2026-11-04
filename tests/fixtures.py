"""
In-memory data fixtures for Cashflow Radar integration tests.
No disk dependencies; no raw research data.
"""

import csv
import datetime
import io
import zipfile
from typing import Any


def generate_csv_bytes(
    rows: list[dict[str, Any]],
    fieldnames: list[str] | None = None,
) -> bytes:
    """
    Generates CSV content as UTF-8 encoded bytes according to template:
    date,amount,direction,category,purpose
    """
    if fieldnames is None:
        fieldnames = ["date", "amount", "direction", "category", "purpose"]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        filtered = {k: ("" if r.get(k) is None else str(r[k])) for k in fieldnames}
        writer.writerow(filtered)

    return output.getvalue().encode("utf-8")


def generate_minimal_xlsx_bytes(
    rows: list[dict[str, Any]],
    sheet_name: str = "transactions",
    headers: list[str] | None = None,
) -> bytes:
    """
    Generates an in-memory valid OpenXML spreadsheet (.xlsx) with standard XML parts:
    - [Content_Types].xml
    - _rels/.rels
    - xl/workbook.xml
    - xl/_rels/workbook.xml.rels
    - xl/worksheets/sheet1.xml
    Does not require openpyxl or external dependencies.
    """
    if headers is None:
        headers = ["date", "amount", "direction", "category", "purpose"]

    col_letters = ["A", "B", "C", "D", "E", "F", "G"]

    sheet_rows_xml = []

    # Header row (row 1)
    header_cells = []
    for col_idx, h in enumerate(headers):
        ref = f"{col_letters[col_idx]}1"
        header_cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{h}</t></is></c>')
    sheet_rows_xml.append(f'<row r="1">{"".join(header_cells)}</row>')

    # Data rows (row 2..N)
    for row_idx, r in enumerate(rows, start=2):
        row_cells = []
        for col_idx, h in enumerate(headers):
            val = r.get(h)
            if val is None or val == "":
                continue
            ref = f"{col_letters[col_idx]}{row_idx}"
            s_val = (
                str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            if h == "amount" and not str(val).startswith("="):
                # Numeric cell
                row_cells.append(f'<c r="{ref}"><v>{s_val}</v></c>')
            elif str(val).startswith("="):
                # Formula cell (for formula rejection test)
                formula_body = s_val[1:]
                row_cells.append(f'<c r="{ref}"><f>{formula_body}</f></c>')
            else:
                # Text cell
                row_cells.append(
                    f'<c r="{ref}" t="inlineStr"><is><t>{s_val}</t></is></c>'
                )
        sheet_rows_xml.append(f'<row r="{row_idx}">{"".join(row_cells)}</row>')

    worksheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows_xml)}</sheetData>"
        "</worksheet>"
    )

    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )

    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{sheet_name}" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )

    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types_xml)
        z.writestr("_rels/.rels", rels_xml)
        z.writestr("xl/workbook.xml", workbook_xml)
        z.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        z.writestr("xl/worksheets/sheet1.xml", worksheet_xml)

    return buf.getvalue()


def build_date_range(end_date_str: str, days_count: int) -> list[str]:
    """Returns a list of consecutive ISO dates ending on end_date_str (inclusive)."""
    end_dt = datetime.date.fromisoformat(end_date_str)
    start_dt = end_dt - datetime.timedelta(days=days_count - 1)
    dates = []
    curr = start_dt
    while curr <= end_dt:
        dates.append(curr.isoformat())
        curr += datetime.timedelta(days=1)
    return dates
