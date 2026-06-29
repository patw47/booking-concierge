"""
Tool: creer_reservation
Sends a booking request to the owner via Telegram (bot the-concierge, same
as property-cm). No write to Google Sheet — the owner handles confirmation.

Env vars required: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
"""

import asyncio
import json
import os
import urllib.request
from datetime import datetime

from loguru import logger
from pipecat.adapters.schemas.direct_function import tool_options
from pipecat.services.llm_service import FunctionCallParams

_TG_API = "https://api.telegram.org/bot{token}/sendMessage"


def _send_telegram(token: str, chat_id: str, text: str) -> bool:
    url = _TG_API.format(token=token)
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        # Telegram always returns HTTP 200; check JSON body for actual success.
        data = json.loads(resp.read())
        return data.get("ok", False)


@tool_options(cancel_on_interruption=False)
async def creer_reservation(
    params: FunctionCallParams,
    nom: str,
    email: str,
    date_debut: str,
    date_fin: str,
    nb_personnes: int,
    notes: str = "",
):
    """Record a booking request and notify the owner via Telegram.

    Args:
        nom: Guest's full name.
        email: Guest's email address.
        date_debut: Requested arrival date in ISO format YYYY-MM-DD.
        date_fin: Requested departure date in ISO format YYYY-MM-DD.
        nb_personnes: Number of guests (1 to 4).
        notes: Optional special requests or remarks from the guest.
    """
    logger.info(f"[tool] creer_reservation({nom}, {date_debut}→{date_fin}, {nb_personnes}p)")
    try:
        token = os.environ["TELEGRAM_TOKEN"]
        chat_id = os.environ["TELEGRAM_CHAT_ID"]

        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
        message = (
            f"🏡 <b>Nouvelle demande de réservation — Villa Eden Bleu</b>\n\n"
            f"👤 <b>Nom :</b> {nom}\n"
            f"📧 <b>Email :</b> {email}\n"
            f"📅 <b>Arrivée :</b> {date_debut}\n"
            f"📅 <b>Départ :</b> {date_fin}\n"
            f"👥 <b>Personnes :</b> {nb_personnes}\n"
        )
        if notes:
            message += f"📝 <b>Notes :</b> {notes}\n"
        message += f"\n⏱ Reçu le {timestamp} via agent vocal"

        success = await asyncio.to_thread(_send_telegram, token, chat_id, message)
        if success:
            logger.info("[tool] Telegram notification sent")
            await params.result_callback({
                "success": True,
                "message": (
                    f"Your booking request has been sent to the owner. "
                    f"They will contact you at {email} within 24 hours to confirm availability and payment."
                ),
            })
        else:
            raise RuntimeError("Telegram API returned non-200")
    except Exception as exc:
        logger.error(f"[tool] creer_reservation error: {exc}")
        await params.result_callback({
            "success": False,
            "message": (
                "I was unable to send your request right now. "
                "Please contact us directly at villaedenbleu@gmail.com or call +33 6 77 67 19 71."
            ),
        })
