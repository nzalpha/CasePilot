import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import backend.agents.agent_decision as agent_decision
import backend.integrations.webex_client as webex_client_module
from backend.integrations.webex_client import WebexClient


class FakeResponse:
    def raise_for_status(self):
        return None


class FakeBadResponse:
    def raise_for_status(self):
        request = httpx.Request("POST", "https://webexapis.com/v1/messages")
        response = httpx.Response(400, request=request)
        raise httpx.HTTPStatusError("Bad request", request=request, response=response)


def test_webex_client_disabled_when_bot_token_missing(monkeypatch):
    monkeypatch.setattr(
        webex_client_module,
        "settings",
        SimpleNamespace(webex_bot_token="", webex_room_id="room-1"),
    )
    client = WebexClient()

    assert client.enabled is False


@pytest.mark.asyncio
async def test_webex_client_disabled_send_returns_false(monkeypatch):
    monkeypatch.setattr(
        webex_client_module,
        "settings",
        SimpleNamespace(webex_bot_token="", webex_room_id="room-1"),
    )
    client = WebexClient()

    result = await client.send_case_notification(
        case_number="0001",
        subject="Router reset",
        question="How do I reset a router?",
        confidence=0.5,
        case_id="case-1",
        salesforce_instance_url="https://example.my.salesforce.com",
    )

    assert result is False


@pytest.mark.asyncio
async def test_webex_client_sends_correct_payload_when_enabled(monkeypatch):
    mock_post = AsyncMock(return_value=FakeResponse())

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.post = mock_post

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(
        webex_client_module,
        "settings",
        SimpleNamespace(webex_bot_token="token-1", webex_room_id="room-1"),
    )
    monkeypatch.setattr(webex_client_module.httpx, "AsyncClient", FakeAsyncClient)
    client = WebexClient()

    result = await client.send_case_notification(
        case_number="0001",
        subject="Router reset",
        question="How do I reset a router?",
        confidence=0.75,
        case_id="case-1",
        salesforce_instance_url="https://example.my.salesforce.com",
    )

    assert result is True
    mock_post.assert_awaited_once()
    _args, kwargs = mock_post.await_args
    assert kwargs["json"]["roomId"] == "room-1"
    markdown = kwargs["json"]["markdown"]
    assert "**🚨 NawazIdea — Human Review Required**" in markdown
    assert "**Case Number:** 0001" in markdown
    assert "**Subject:** Router reset" in markdown
    assert "**Confidence Score:** 75%" in markdown
    assert "**Question:** How do I reset a router?" in markdown
    assert (
        "https://example.my.salesforce.com/lightning/r/Case/case-1/view"
        in markdown
    )


@pytest.mark.asyncio
async def test_webex_client_returns_false_and_logs_when_http_call_fails(
    monkeypatch,
    caplog,
):
    mock_post = AsyncMock(return_value=FakeBadResponse())

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.post = mock_post

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(
        webex_client_module,
        "settings",
        SimpleNamespace(webex_bot_token="token-1", webex_room_id="room-1"),
    )
    monkeypatch.setattr(webex_client_module.httpx, "AsyncClient", FakeAsyncClient)
    client = WebexClient()

    result = await client.send_case_notification(
        case_number="0001",
        subject="Router reset",
        question="How do I reset a router?",
        confidence=0.5,
        case_id="case-1",
        salesforce_instance_url="https://example.my.salesforce.com",
    )

    assert result is False
    assert "Failed to send Webex case notification" in caplog.text


@pytest.mark.asyncio
async def test_handle_low_confidence_calls_send_case_notification(monkeypatch):
    class FakeWebexClient:
        instances = []

        def __init__(self):
            self.send_case_notification = AsyncMock(return_value=True)
            self.instances.append(self)

    sf_client = SimpleNamespace(flag_for_human_review=MagicMock(return_value=True))
    fake_case_store = SimpleNamespace(add=MagicMock())
    monkeypatch.setattr(agent_decision, "WebexClient", FakeWebexClient)
    monkeypatch.setattr(agent_decision, "case_store", fake_case_store)
    monkeypatch.setattr(
        agent_decision,
        "settings",
        SimpleNamespace(salesforce_instance_url="https://example.my.salesforce.com"),
    )

    await agent_decision.handle_low_confidence(
        sf_client=sf_client,
        case={
            "case_number": "0001",
            "subject": "Router reset",
        },
        case_id="case-1",
        confidence=0.5,
        question="How do I reset a router?",
    )

    sf_client.flag_for_human_review.assert_called_once_with(
        "case-1",
        0.5,
        "How do I reset a router?",
    )
    FakeWebexClient.instances[0].send_case_notification.assert_awaited_once_with(
        case_number="0001",
        subject="Router reset",
        question="How do I reset a router?",
        confidence=0.5,
        case_id="case-1",
        salesforce_instance_url="https://example.my.salesforce.com",
    )
