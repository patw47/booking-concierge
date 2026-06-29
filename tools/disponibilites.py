"""
Tool: get_disponibilites
Reads the Villa Eden Bleu Google Sheet calendar and returns whether a date range
is available. Booked periods are rows in the sheet (date_debut, date_fin).

Sheet structure expected (configurable via GOOGLE_SHEET_RANGE):
  Column A: arrival date   (DD/MM/YYYY or YYYY-MM-DD)
  Column B: departure date (DD/MM/YYYY or YYYY-MM-DD)

Auth: service account property-cm-agent@property-cm.iam.gserviceaccount.com
      Key file path set via GOOGLE_SERVICE_ACCOUNT_FILE env var. Headless, no browser.
"""

import asyncio
import os
from datetime import date, datetime
from pathlib import Path

from loguru import logger
from pipecat.adapters.schemas.direct_function import tool_options
from pipecat.services.llm_service import FunctionCallParams

from google.oauth2 import service_account
from googleapiclient.discovery import build

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def _parse_date(s: str) -> date | None:
    """Parse DD/MM/YYYY or YYYY-MM-DD. Return None if unparseable."""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
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


def _booked_periods() -> list[tuple[date, date]]:
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    sheet_range = os.environ.get("GOOGLE_SHEET_RANGE", "Calendrier!A2:B")
    svc = _sheets_service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=sheet_range,
    ).execute()
    rows = result.get("values", [])
    periods = []
    for row in rows:
        if len(row) < 2:
            continue
        start = _parse_date(row[0])
        end = _parse_date(row[1])
        if start and end:
            periods.append((start, end))
    return periods


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
                "message": "Departure must be after arrival.",
            })
            return

        booked = await asyncio.to_thread(_booked_periods)
        conflicts = [
            (s, e) for s, e in booked
            if s < req_end and e > req_start  # overlap check
        ]

        if not conflicts:
            await params.result_callback({
                "disponible": True,
                "message": (
                    f"Villa Eden Bleu is available from {req_start.strftime('%d %B %Y')} "
                    f"to {req_end.strftime('%d %B %Y')}."
                ),
            })
        else:
            conflict_strs = [
                f"{s.strftime('%d %B')} – {e.strftime('%d %B %Y')}" for s, e in conflicts
            ]
            await params.result_callback({
                "disponible": False,
                "message": (
                    f"Villa Eden Bleu is not available for those dates. "
                    f"Conflicting booking(s): {', '.join(conflict_strs)}."
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
