from __future__ import annotations

import asyncio
import logging

import httpx

from backend.agents.agent_decision import (
    handle_high_confidence,
    handle_low_confidence,
)
from backend.config import settings
from backend.integrations.salesforce_client import SalesforceClient
from backend.agents.reply_handler import handle_case_reply


logger = logging.getLogger(__name__)


def build_question(case: dict) -> str:
    question = case["subject"]
    if case["description"]:
        question = case["subject"] + " " + case["description"]
    return question


async def process_case(
    case: dict,
    sf_client: SalesforceClient,
    retrieval_base_url: str,
) -> None:
    try:
        question = build_question(case)
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{retrieval_base_url}/api/v1/retriever",
                params={
                    "question": question,
                    "session_id": case["case_id"],
                    "mode": "graph_vector_fulltext",
                    "response_type": "answer",
                    "top_k": 5,
                },
                data={"database": "nawazidea_kb"},
            )
            response.raise_for_status()
            payload = response.json()

        answer = payload["data"]["message"]
        confidence = payload["data"]["info"]["confidence"]
        sources = payload["data"]["info"]["sources"]

        if confidence >= settings.confidence_threshold:
            await handle_high_confidence(
                sf_client,
                case,
                case["case_id"],
                question,
                answer,
                sources,
                confidence,
            )
        else:
            await handle_low_confidence(
                sf_client,
                case,
                case["case_id"],
                confidence,
                question,
            )
    except Exception as exc:
        logger.exception("Failed to process Salesforce case %s: %s", case.get("case_id"), exc)


async def poll_loop(retrieval_base_url: str) -> None:
    sf_client = SalesforceClient()
    if sf_client.sf is None:
        logger.warning("Salesforce polling disabled because Salesforce is unavailable")
        return

    try:
        while True:
            cases = sf_client.get_new_cases()
            for case in cases:
                await process_case(case, sf_client, retrieval_base_url)
            await asyncio.sleep(settings.salesforce_poll_interval)
    except asyncio.CancelledError:
        logger.info("Salesforce polling stopped")
        raise


async def start_poll_loop(retrieval_base_url: str) -> asyncio.Task:
    return asyncio.create_task(poll_loop(retrieval_base_url))


async def reply_poll_loop(retrieval_base_url: str) -> None:
    sf_client = SalesforceClient()
    if sf_client.sf is None:
        logger.warning("Reply polling disabled because Salesforce is unavailable")
        return
    try:
        while True:
            cases = sf_client.get_inprogress_cases()
            for case in cases:
                replies = sf_client.get_new_customer_replies(
                    case["case_id"],
                    case.get("last_reply_checked"),
                )
                if replies:
                    await handle_case_reply(case, replies, sf_client, retrieval_base_url)
            await asyncio.sleep(settings.reply_poll_interval)
    except asyncio.CancelledError:
        logger.info("Reply polling stopped")
        raise


async def start_reply_poll_loop(retrieval_base_url: str) -> asyncio.Task:
    return asyncio.create_task(reply_poll_loop(retrieval_base_url))
