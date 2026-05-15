from __future__ import annotations

import logging

from backend.integrations.salesforce_client import SalesforceClient


logger = logging.getLogger(__name__)


async def handle_high_confidence(
    sf_client: SalesforceClient,
    case_id: str,
    answer: str,
    sources: list[str],
    confidence: float,
) -> None:
    sf_client.post_answer_to_case(case_id, answer, sources, confidence)
    logger.info(
        "Case %s answered automatically. confidence=%.2f",
        case_id,
        confidence,
    )


async def handle_low_confidence(
    sf_client: SalesforceClient,
    case_id: str,
    confidence: float,
    question: str,
) -> None:
    sf_client.flag_for_human_review(case_id, confidence, question)
    logger.info(
        "Case %s flagged for human review. confidence=%.2f",
        case_id,
        confidence,
    )
