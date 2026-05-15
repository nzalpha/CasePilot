from __future__ import annotations

import logging

from backend.integrations.salesforce_client import SalesforceClient
from backend.models.case_store import CaseRecord, case_store
from backend.routers.ingestion import utc_now_iso


logger = logging.getLogger(__name__)


async def handle_high_confidence(
    sf_client: SalesforceClient,
    case: dict,
    case_id: str,
    question: str,
    answer: str,
    sources: list[str],
    confidence: float,
) -> None:
    sf_client.post_answer_to_case(case_id, answer, sources, confidence)
    case_store.add(
        CaseRecord(
            case_id=case_id,
            case_number=case.get("case_number", ""),
            subject=case.get("subject", ""),
            question=question,
            action="auto_answered",
            confidence=confidence,
            answer=answer,
            sources=sources,
            processed_at=utc_now_iso(),
            status="processed",
        )
    )
    logger.info(
        "Case %s answered automatically. confidence=%.2f",
        case_id,
        confidence,
    )


async def handle_low_confidence(
    sf_client: SalesforceClient,
    case: dict,
    case_id: str,
    confidence: float,
    question: str,
) -> None:
    sf_client.flag_for_human_review(case_id, confidence, question)
    case_store.add(
        CaseRecord(
            case_id=case_id,
            case_number=case.get("case_number", ""),
            subject=case.get("subject", ""),
            question=question,
            action="flagged_for_human",
            confidence=confidence,
            answer=None,
            sources=[],
            processed_at=utc_now_iso(),
            status="processed",
        )
    )
    logger.info(
        "Case %s flagged for human review. confidence=%.2f",
        case_id,
        confidence,
    )
