"""
Tool: creer_reservation
Writes a booking request row to Google Sheet and sends a Gmail confirmation.
Implementation: Sprint 2.
"""


async def creer_reservation(
    name: str,
    email: str,
    checkin: str,
    checkout: str,
    guests: int,
    notes: str = "",
) -> dict:
    """
    Returns:
        {"success": bool, "reference": str, "message": str}
    """
    raise NotImplementedError("Sprint 2")
