from __future__ import annotations

import logging

import httpx

from backend.config import settings


logger = logging.getLogger(__name__)


class WebexClient:
    def __init__(self) -> None:
        self.bot_token = settings.webex_bot_token
        self.room_id = settings.webex_room_id
        self.enabled = True
        if not self.bot_token or not self.room_id:
            logger.warning("Webex settings are incomplete; notifications are disabled")
            self.enabled = False

    async def send_case_notification(
        self,
        case_number: str,
        subject: str,
        question: str,
        confidence: float,
        case_id: str,
        salesforce_instance_url: str,
    ) -> bool:
        if not self.enabled:
            return False

        salesforce_url = (
            f"{salesforce_instance_url.rstrip('/')}/lightning/r/Case/{case_id}/view"
        )
        markdown = "\n\n".join(
            [
                "**🚨 NawazIdea — Human Review Required**",
                f"**Case Number:** {case_number}",
                f"**Subject:** {subject}",
                f"**Confidence Score:** {confidence:.0%}",
                f"**Question:** {question}",
                f"**Salesforce Case:** [Open Case]({salesforce_url})",
                "Please review, edit the AI draft in Salesforce if present, and respond.",
            ]
        )

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://webexapis.com/v1/messages",
                    headers={
                        "Authorization": f"Bearer {self.bot_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "roomId": self.room_id,
                        "markdown": markdown,
                    },
                )
                response.raise_for_status()
            return True
        except Exception as exc:
            logger.exception("Failed to send Webex case notification: %s", exc)
            return False
