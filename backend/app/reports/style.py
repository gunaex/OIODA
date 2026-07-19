import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from fastapi.responses import StreamingResponse

HEADER_FILL = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF")
BODY_FONT = Font(name="Calibri")
TITLE_FONT = Font(name="Calibri", bold=True, size=13)
SECTION_FONT = Font(name="Calibri", bold=True, size=11)


def write_title(ws, row: int, text: str) -> int:
    ws.cell(row=row, column=1, value=text).font = TITLE_FONT
    return row + 2


def write_section(ws, row: int, text: str) -> int:
    ws.cell(row=row, column=1, value=text).font = SECTION_FONT
    return row + 1


def write_table(ws, start_row: int, headers: list[str], rows: list[dict]) -> int:
    """Writes a styled header row followed by data rows starting at
    `start_row`. Returns the next free row after the table."""
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=start_row, column=c, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="left")

    r = start_row + 1
    for row in rows:
        for c, h in enumerate(headers, start=1):
            value = row.get(h)
            cell = ws.cell(row=r, column=c, value=value)
            cell.font = BODY_FONT
        r += 1

    for c, h in enumerate(headers, start=1):
        col_letter = get_column_letter(c)
        width = max(len(h) + 2, 12)
        ws.column_dimensions[col_letter].width = min(width, 40)

    return r + 1


def workbook_response(wb: Workbook, filename: str) -> StreamingResponse:
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
