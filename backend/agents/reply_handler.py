from __future__ import annotations

import logging
from datetime import datetime

import httpx

from backend.agents.reply_classifier import classify_reply
from backend.agents.self_learner import generate_kb_article_body, ingest_resolved_qa
from backend.config import settings
from backend.integrations.salesforce_client import SalesforceClient
from backend.integrations.webex_client import WebexClient
from backend.models.case_store import case_store


logger = logging.getLogger(__name__)


async def send_webex_message(markdown: str) -> bool:
    webex_client = WebexClient()
    if not webex_client.enabled:
        return False

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://webexapis.com/v1/messages",
                headers={
                    "Authorization": f"Bearer {webex_client.bot_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "roomId": webex_client.room_id,
                    "markdown": markdown,
                },
            )
            response.raise_for_status()
        return True
    except Exception as exc:
        logger.exception("Failed to send Webex reply notification: %s", exc)
        return False


async def call_retriever(
    retrieval_base_url: str,
    case_id: str,
    question: str,
) -> dict:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{retrieval_base_url}/api/v1/retriever",
            params={
                "question": question,
                "session_id": case_id,
                "mode": "graph_vector_fulltext",
                "response_type": "answer",
                "top_k": 5,
            },
            data={"database": "nawazidea_kb"},
        )
        response.raise_for_status()
        return response.json()


async def handle_case_reply(
    case: dict,
    replies: list[str],
    sf_client: SalesforceClient,
    retrieval_base_url: str,
) -> None:
    combined_reply = " ".join(replies)
    try:
        intent = await classify_reply(combined_reply)
        if intent == "SATISFIED":
            sf_client.close_case(case["case_id"])
            case_store.update_status(case["case_id"], "resolved")
            question = case["subject"] + " " + case.get("description", "")
            kb_link = None
            if settings.self_learning_enabled:
                # Fetch full case history so GPT can write a proper KB article
                case_history = sf_client.get_case_history(case["case_id"])
                kb_body = await generate_kb_article_body(case_history)
                await ingest_resolved_qa(question, kb_body, case["case_number"])
                article_id = sf_client.create_knowledge_article(
                    title=case["subject"],
                    summary=f"Resolved case {case['case_number']} — auto-generated",
                    body=kb_body,
                )
                if article_id:
                    kb_link = (
                        f"{settings.salesforce_instance_url.rstrip('/')}"
                        f"/lightning/r/Knowledge__kav/{article_id}/view"
                    )

            kb_line = (
                f"\n\n📄 **Knowledge Article:** [Review Draft]({kb_link})"
                if kb_link else ""
            )
            await send_webex_message(
                f"✅ **Case {case['case_number']} — Auto-Closed**\n\n"
                f"**Subject:** {case['subject']}\n\n"
                f"Customer confirmed the issue is resolved.{kb_line}"
            )

        elif intent == "STUCK":
            # Customer says the solution did not work — notify engineer immediately.
            # Do NOT auto-post another AI answer on a case already in progress.
            sf_client.flag_for_human_review(
                case["case_id"],
                0.0,
                combined_reply,
            )
            await send_webex_message(
                f"⚠️ **Case {case['case_number']} — Customer Still Stuck**\n\n"
                f"**Subject:** {case['subject']}\n\n"
                f"**Customer reply:** {combined_reply}\n\n"
                "The previous answer did not resolve the issue. Please review and respond manually."
            )

        else:
            # UNCLEAR — customer may be asking for a call, meeting, or human help
            await send_webex_message(
                f"❓ **Case {case['case_number']} — Human Assistance Requested**\n\n"
                f"**Subject:** {case['subject']}\n\n"
                f"**Customer reply:** {combined_reply}\n\n"
                "Please review and respond — customer may be requesting a call or direct help."
            )
    except Exception as exc:
        logger.exception("Failed to handle reply for case %s: %s", case.get("case_id"), exc)
    finally:
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        sf_client.update_last_reply_checked(case["case_id"], now_iso)
