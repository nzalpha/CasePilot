from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response

from backend.integrations.salesforce_client import SalesforceClient
from backend.models.case_store import CaseRecord, case_store
from backend.models.schemas import (
    CaseActionResponse,
    CaseResponse,
    CaseSummaryResponse,
)


logger = logging.getLogger(__name__)
router = APIRouter()
sf_client = SalesforceClient()


def record_to_response(record: CaseRecord) -> CaseResponse:
    return CaseResponse(
        case_id=record.case_id,
        case_number=record.case_number,
        subject=record.subject,
        question=record.question,
        action=record.action,
        confidence=record.confidence,
        answer=record.answer,
        sources=record.sources,
        processed_at=record.processed_at,
        status=record.status,
    )


@router.get("/cases", response_model=list[CaseResponse])
def list_cases(response: Response) -> list[CaseResponse]:
    summary = case_store.summary()
    response.headers["X-Total"] = str(summary["total"])
    response.headers["X-Auto-Answered"] = str(summary["auto_answered"])
    response.headers["X-Flagged"] = str(summary["flagged_for_human"])
    return [record_to_response(record) for record in case_store.all()]


@router.get("/cases/summary", response_model=CaseSummaryResponse)
def get_cases_summary() -> CaseSummaryResponse:
    return CaseSummaryResponse(**case_store.summary())


@router.get("/cases/{case_id}", response_model=CaseResponse)
def get_case(case_id: str) -> CaseResponse:
    record = case_store.get(case_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return record_to_response(record)


@router.post("/cases/{case_id}/resolve", response_model=CaseActionResponse)
def resolve_case(case_id: str) -> CaseActionResponse:
    if case_store.get(case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")

    case_store.update_status(case_id, "resolved")
    if sf_client.sf is None:
        logger.warning("Salesforce unavailable; case %s resolved only in local store", case_id)
    else:
        try:
            sf_client.sf.Case.update(case_id, {"Status": "Closed"})
        except Exception as exc:
            logger.exception("Failed to close Salesforce case %s: %s", case_id, exc)

    return CaseActionResponse(
        case_id=case_id,
        status="resolved",
        message=f"Case {case_id} marked as resolved",
    )


@router.post("/cases/{case_id}/escalate", response_model=CaseActionResponse)
def escalate_case(case_id: str) -> CaseActionResponse:
    if case_store.get(case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")

    case_store.update_status(case_id, "escalated")
    if sf_client.sf is None:
        logger.warning("Salesforce unavailable; case %s escalated only in local store", case_id)
    else:
        try:
            sf_client.sf.Case.update(case_id, {"Priority": "High"})
            sf_client.sf.CaseComment.create(
                {
                    "ParentId": case_id,
                    "CommentBody": "[NawazIdea] Case manually escalated.",
                    "IsPublished": False,
                }
            )
        except Exception as exc:
            logger.exception("Failed to escalate Salesforce case %s: %s", case_id, exc)

    return CaseActionResponse(
        case_id=case_id,
        status="escalated",
        message=f"Case {case_id} marked as escalated",
    )
