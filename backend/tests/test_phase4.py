import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import backend.routers.cases as cases_router
from backend.models.case_store import CaseRecord, CaseStore


def make_record(
    case_id="case-1",
    action="auto_answered",
    status="processed",
) -> CaseRecord:
    return CaseRecord(
        case_id=case_id,
        case_number="0001",
        subject="Router reset",
        question="How do I reset a router?",
        action=action,
        confidence=0.91,
        answer="Hold the reset button for ten seconds."
        if action == "auto_answered"
        else None,
        sources=["manual.pdf"] if action == "auto_answered" else [],
        processed_at="2026-05-15T12:00:00+00:00",
        status=status,
    )


def test_case_store_add_and_get():
    store = CaseStore()
    record = make_record()

    store.add(record)

    assert store.get("case-1") == record


def test_case_store_update_status():
    store = CaseStore()
    store.add(make_record())

    updated = store.update_status("case-1", "resolved")

    assert updated is True
    assert store.get("case-1").status == "resolved"


def test_case_store_summary_counts():
    store = CaseStore()
    store.add(make_record(case_id="case-1", action="auto_answered"))
    store.add(make_record(case_id="case-2", action="auto_answered", status="resolved"))
    store.add(
        make_record(
            case_id="case-3",
            action="flagged_for_human",
            status="escalated",
        )
    )

    assert store.summary() == {
        "total": 3,
        "auto_answered": 2,
        "flagged_for_human": 1,
        "resolved": 1,
        "escalated": 1,
    }


class FakeCaseStore:
    def __init__(self, records):
        self.records = {record.case_id: record for record in records}

    def all(self):
        return list(self.records.values())

    def summary(self):
        records = list(self.records.values())
        return {
            "total": len(records),
            "auto_answered": sum(
                1 for record in records if record.action == "auto_answered"
            ),
            "flagged_for_human": sum(
                1 for record in records if record.action == "flagged_for_human"
            ),
            "resolved": sum(1 for record in records if record.status == "resolved"),
            "escalated": sum(1 for record in records if record.status == "escalated"),
        }

    def get(self, case_id):
        return self.records.get(case_id)

    def update_status(self, case_id, status):
        record = self.records.get(case_id)
        if record is None:
            return False
        record.status = status
        return True


def build_client(monkeypatch, fake_store):
    app = FastAPI()
    monkeypatch.setattr(cases_router, "case_store", fake_store)
    monkeypatch.setattr(cases_router, "sf_client", SimpleNamespace(sf=None))
    app.include_router(cases_router.router)
    return TestClient(app)


def test_cases_endpoint_returns_list(monkeypatch):
    client = build_client(
        monkeypatch,
        FakeCaseStore(
            [
                make_record(case_id="case-1"),
                make_record(case_id="case-2", action="flagged_for_human"),
            ]
        ),
    )

    response = client.get("/cases")

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.headers["X-Total"] == "2"
    assert response.headers["X-Auto-Answered"] == "1"
    assert response.headers["X-Flagged"] == "1"


def test_cases_detail_endpoint_not_found(monkeypatch):
    client = build_client(monkeypatch, FakeCaseStore([]))

    response = client.get("/cases/nonexistent-id")

    assert response.status_code == 404
    assert response.json() == {"detail": "Case not found"}


def test_resolve_endpoint_updates_status(monkeypatch):
    fake_store = FakeCaseStore([make_record(case_id="case-1")])
    client = build_client(monkeypatch, fake_store)

    response = client.post("/cases/case-1/resolve")

    assert response.status_code == 200
    assert response.json() == {
        "case_id": "case-1",
        "status": "resolved",
        "message": "Case case-1 marked as resolved",
    }
    assert fake_store.get("case-1").status == "resolved"
