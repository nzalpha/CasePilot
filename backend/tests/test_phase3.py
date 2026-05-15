import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import backend.agents.case_listener as case_listener
from backend.integrations.salesforce_client import (
    SalesforceClient,
    build_answer_comment,
    build_flag_comment,
)


def test_get_new_cases_returns_empty_when_sf_is_none():
    sf_client = object.__new__(SalesforceClient)
    sf_client.sf = None

    assert sf_client.get_new_cases() == []


def test_build_answer_comment_contains_confidence_and_answer():
    comment = build_answer_comment(
        answer="Reset the router from the admin page.",
        sources=["https://example.com/router-reset", "manual.pdf"],
        confidence=0.95,
    )

    assert "Reset the router from the admin page." in comment
    assert "Confidence: 95%" in comment
    assert "https://example.com/router-reset" in comment
    assert "manual.pdf" in comment


def test_build_flag_comment_contains_confidence_and_question():
    comment = build_flag_comment(
        confidence=0.5,
        question="How do I reset a router?",
    )

    assert "Confidence score 50% is below threshold." in comment
    assert "Question: How do I reset a router?" in comment


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeAsyncClient:
    payload = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, *args, **kwargs):
        return FakeResponse(self.payload)


class MockSalesforceClient:
    def __init__(self):
        self.post_answer_calls = []
        self.flag_for_human_calls = []

    def post_answer_to_case(self, case_id, answer, sources, confidence):
        self.post_answer_calls.append(
            {
                "case_id": case_id,
                "answer": answer,
                "sources": sources,
                "confidence": confidence,
            }
        )
        return True

    def flag_for_human_review(self, case_id, confidence, question):
        self.flag_for_human_calls.append(
            {
                "case_id": case_id,
                "confidence": confidence,
                "question": question,
            }
        )
        return True


def retrieval_payload(confidence):
    return {
        "status": "Success",
        "data": {
            "session_id": "case-1",
            "message": "Use the reset button for ten seconds.",
            "info": {
                "sources": ["manual.pdf"],
                "model": "gpt-4o",
                "nodedetails": {"chunkdetails": []},
                "response_time": 0.1,
                "mode": "graph_vector_fulltext",
                "confidence": confidence,
            },
        },
    }


@pytest.mark.asyncio
async def test_process_case_high_confidence_calls_post_answer(monkeypatch):
    FakeAsyncClient.payload = retrieval_payload(0.95)
    monkeypatch.setattr(case_listener.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        case_listener,
        "settings",
        SimpleNamespace(confidence_threshold=0.8),
    )
    sf_client = MockSalesforceClient()

    await case_listener.process_case(
        {
            "case_id": "case-1",
            "case_number": "0001",
            "subject": "How do I reset a router?",
            "description": "The reset page is not obvious.",
            "status": "New",
        },
        sf_client,
        "http://testserver",
    )

    assert sf_client.post_answer_calls == [
        {
            "case_id": "case-1",
            "answer": "Use the reset button for ten seconds.",
            "sources": ["manual.pdf"],
            "confidence": 0.95,
        }
    ]
    assert sf_client.flag_for_human_calls == []


@pytest.mark.asyncio
async def test_process_case_low_confidence_calls_flag_for_human(monkeypatch):
    FakeAsyncClient.payload = retrieval_payload(0.5)
    monkeypatch.setattr(case_listener.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        case_listener,
        "settings",
        SimpleNamespace(confidence_threshold=0.8),
    )
    sf_client = MockSalesforceClient()

    await case_listener.process_case(
        {
            "case_id": "case-2",
            "case_number": "0002",
            "subject": "How do I reset a router?",
            "description": "",
            "status": "New",
        },
        sf_client,
        "http://testserver",
    )

    assert sf_client.post_answer_calls == []
    assert sf_client.flag_for_human_calls == [
        {
            "case_id": "case-2",
            "confidence": 0.5,
            "question": "How do I reset a router?",
        }
    ]
