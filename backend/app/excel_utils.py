import io
from datetime import date, datetime
from typing import Any

import pandas as pd
from fastapi import HTTPException
from fastapi.responses import StreamingResponse


def make_excel_response(rows: list[dict], columns: list[str], filename: str) -> StreamingResponse:
    df = pd.DataFrame(rows, columns=columns)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def make_template_response(columns: list[str], filename: str) -> StreamingResponse:
    return make_excel_response([], columns, filename)


def read_import_excel(file_bytes: bytes, expected_columns: list[str]) -> list[dict[str, Any]]:
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read Excel file: {exc}")

    actual_columns = [str(c).strip() for c in df.columns]
    missing = [c for c in expected_columns if c not in actual_columns]
    unexpected = [c for c in actual_columns if c not in expected_columns]

    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Column headers do not match the import template.",
                "missing_columns": missing,
                "unexpected_columns": unexpected,
                "expected_columns": expected_columns,
            },
        )

    df = df[expected_columns]
    df = df.where(pd.notnull(df), None)

    records = df.to_dict(orient="records")
    for record in records:
        for key, value in record.items():
            if isinstance(value, pd.Timestamp):
                record[key] = value.date()
            elif value is not None and not isinstance(value, (str, int, float, bool, date, datetime)):
                record[key] = str(value)
    return records
