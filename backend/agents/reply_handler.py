from __future__ import annotations

import logging
from datetime import datetime

import httpx

from backend.agents.reply_classifier import classify_reply
from backend.agents.self_learner import ingest_resolved_qa
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
            if settings.self_learning_enabled:
                await ingest_resolved_qa(question, combined_reply, case["case_number"])
                sf_client.create_knowledge_article(
                    title=case["subject"],
                    summary=(
                        f"Resolved case {case['case_number']} — auto-generated"
                    ),
                    body=(
                        f"Question:\n{question}\n\n"
                        f"Resolution confirmed by customer:\n{combined_reply}"
                    ),
                )
            await send_webex_message(
                (
                    f"✅ Case {case['case_number']} has been auto-closed. "
                    "Customer confirmed resolution.\n"
                    "A draft knowledge article has been created for review."
                )
            )

        elif intent == "STUCK":
            retrieval_response = await call_retriever(
                retrieval_base_url,
                case["case_id"],
                combined_reply,
            )
            answer = retrieval_response["data"]["message"]
            confidence = retrieval_response["data"]["info"]["confidence"]
            sources = retrieval_response["data"]["info"]["sources"]
            if confidence >= settings.confidence_threshold:
                sf_client.post_answer_to_case(
                    case["case_id"],
                    answer,
                    sources,
                    confidence,
                )
            else:
                sf_client.flag_for_human_review(
                    case["case_id"],
                    confidence,
                    combined_reply,
                )
                await send_webex_message(
                    (
                        f"⚠️ Case {case['case_number']} customer replied but AI "
                        "still not confident.\nPlease review manually."
                    )
                )

        else:
            await send_webex_message(
                (
                    f"❓ Case {case['case_number']} has a new customer reply that "
                    "needs manual review.\nIntent could not be determined."
                )
            )
    except Exception as exc:
        logger.exception("Failed to handle reply for case %s: %s", case.get("case_id"), exc)
    finally:
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        sf_client.update_last_reply_checked(case["case_id"], now_iso)
