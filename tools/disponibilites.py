"""
Tool: get_disponibilites
Reads the Villa Eden Bleu Google Sheet calendar.

Sheet structure:
  - One tab per month, named "Mois YYYY" (e.g. "Mars 2026")
  - Column A: one date per row (one row per day)
  - Column C: guest name — MERGED vertically across multi-day stays.
              The name appears only in the first cell of the merge;
              subsequent rows of the same booking appear empty.
              A date is FREE if column C is empty AND not part of a vertical merge.

Auth: service account property-cm-agent@property-cm.iam.gserviceaccount.com
"""

import asyncio
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from loguru import logger
from pipecat.adapters.schemas.direct_function import tool_options
from pipecat.services.llm_service import FunctionCallParams

from google.oauth2 import service_account
from googleapiclient.discovery import build

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

_FRENCH_MONTHS = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]


def _sheet_tab(d: date) -> str:
    return f"{_FRENCH_MONTHS[d.month - 1]} {d.year}"


def _months_between(start: date, end: date) -> list[str]:
    """All monthly tab names covering start..end (inclusive)."""
    tabs, cur = [], date(start.year, start.month, 1)
    ceil = date(end.year, end.month, 1)
    while cur <= ceil:
        tabs.append(_sheet_tab(cur))
        cur = date(cur.year + (cur.month == 12), (cur.month % 12) + 1, 1)
    return tabs


def _parse_date(s: str) -> date | None:
    for fmt in ("%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _sheets_service():
    key_file = Path(os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "property-cm-agent-key.json"))
    creds = service_account.Credentials.from_service_account_file(
        str(key_file), scopes=_SCOPES
    )
    return build("sheets", "v4", credentials=creds)


def _booked_dates_for_tabs(tabs: list[str]) -> set[date]:
    """
    Read the requested monthly tabs and return the set of booked dates.

    Uses spreadsheets.get(includeGridData=True) to access both cell values
    and merge metadata — needed because column C is merged vertically across
    multi-day stays and .values().get() would miss the continuation rows.
    """
    if not tabs:
        return set()

    svc = _sheets_service()
    sheet_id = os.environ["GOOGLE_SHEET_ID"]

    # 1. Filter to tabs that actually exist in the spreadsheet.
    meta = svc.spreadsheets().get(
        spreadsheetId=sheet_id,
        fields="sheets.properties.title",
    ).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
    valid_tabs = [t for t in tabs if t in existing]
    if not valid_tabs:
        return set()

    # 2. Fetch grid data + merge info for each valid tab.
    result = svc.spreadsheets().get(
        spreadsheetId=sheet_id,
        ranges=[f"{t}!A:C" for t in valid_tabs],
        includeGridData=True,
    ).execute()

    booked: set[date] = set()

    for sheet in result.get("sheets", []):
        # Build set of row indices that are inside a vertical merge on column C (index 2).
        # Merge covers startRowIndex (inclusive) to endRowIndex (exclusive).
        merged_row_indices: set[int] = set()
        for merge in sheet.get("merges", []):
            col_start = merge.get("startColumnIndex", 0)
            col_end = merge.get("endColumnIndex", 0)
            if col_start <= 2 < col_end:
                for r in range(merge["startRowIndex"], merge["endRowIndex"]):
                    merged_row_indices.add(r)

        grid_data = sheet.get("data", [])
        if not grid_data:
            continue
        rows = grid_data[0].get("rowData", [])

        for row_idx, row in enumerate(rows):
            cells = row.get("values", [])

            # Column A: date string
            if not cells:
                continue
            date_str = cells[0].get("formattedValue", "")
            d = _parse_date(date_str)
            if not d:
                continue

            # Column C: guest name (index 2)
            name_val = ""
            if len(cells) >= 3:
                name_val = (cells[2].get("formattedValue") or "").strip()

            # Booked if C has a value (single-day or start of merge)
            # OR row is inside a merge range (continuation of a multi-day stay).
            if name_val or row_idx in merged_row_indices:
                booked.add(d)

    return booked


@tool_options(cancel_on_interruption=False)
async def get_disponibilites(
    params: FunctionCallParams,
    date_debut: str,
    date_fin: str,
):
    """Check availability for Villa Eden Bleu for a given date range.

    Args:
        date_debut: Requested arrival date in ISO format YYYY-MM-DD.
        date_fin: Requested departure date in ISO format YYYY-MM-DD.
    """
    logger.info(f"[tool] get_disponibilites({date_debut} → {date_fin})")
    try:
        req_start = _parse_date(date_debut)
        req_end = _parse_date(date_fin)

        if not req_start or not req_end:
            await params.result_callback({
                "disponible": False,
                "message": "Invalid date format. Please use YYYY-MM-DD.",
            })
            return
        if req_end <= req_start:
            await params.result_callback({
                "disponible": False,
                "message": "Departure date must be after arrival date.",
            })
            return

        tabs = _months_between(req_start, req_end)
        booked = await asyncio.to_thread(_booked_dates_for_tabs, tabs)

        # Check every night of the stay (arrival inclusive, departure exclusive).
        stay_nights = [req_start + timedelta(days=i) for i in range((req_end - req_start).days)]
        conflicts = [d for d in stay_nights if d in booked]

        if not conflicts:
            await params.result_callback({
                "disponible": True,
                "message": (
                    f"Villa Eden Bleu is available from {req_start.strftime('%d %B %Y')} "
                    f"to {req_end.strftime('%d %B %Y')}."
                ),
            })
        else:
            conflict_strs = ", ".join(d.strftime("%d %B %Y") for d in conflicts[:3])
            suffix = " and more" if len(conflicts) > 3 else ""
            await params.result_callback({
                "disponible": False,
                "message": (
                    f"Villa Eden Bleu is not available for those dates. "
                    f"Booked day(s) in your range: {conflict_strs}{suffix}."
                ),
            })

    except Exception as exc:
        logger.error(f"[tool] get_disponibilites error: {exc}")
        await params.result_callback({
            "disponible": False,
            "message": (
                "I was unable to check availability right now. "
                "Please contact us at villaedenbleu@gmail.com or call +33 6 77 67 19 71."
            ),
        })
