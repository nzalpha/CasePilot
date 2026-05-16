import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import backend.agents.reply_handler as reply_handler
import backend.agents.self_learner as self_learner
from backend.agents.reply_classifier import classify_reply
from backend.integrations.salesforce_client import SalesforceClient


class FakeSalesforce:
    def __init__(self, query_result=None):
        self.query_result = query_result or {"records": []}
        self.Case = SimpleNamespace(update=MagicMock())
        self.CaseComment = SimpleNamespace(create=MagicMock())
        self.Knowledge__kav = SimpleNamespace(create=MagicMock())

    def query(self, query):
        return self.query_result


def build_sf_client(fake_salesforce):
    client = object.__new__(SalesforceClient)
    client.sf = fake_salesforce
    return client


def test_get_inprogress_cases_returns_correctly_shaped_dicts():
    sf_client = build_sf_client(
        FakeSalesforce(
            {
                "records": [
                    {
                        "Id": "case-1",
                        "CaseNumber": "0001",
                        "Subject": "Router reset",
                        "Description": "Cannot reset",
                        "Status": "In Progress",
                        "CasePilot1_LastReplyChecked_c__c": "2026-05-15T10:00:00Z",
                    }
                ]
            }
        )
    )

    assert sf_client.get_inprogress_cases() == [
        {
            "case_id": "case-1",
            "case_number": "0001",
            "subject": "Router reset",
            "description": "Cannot reset",
            "last_reply_checked": "2026-05-15T10:00:00Z",
        }
    ]


def test_get_new_customer_replies_filters_by_published_and_timestamp():
    sf_client = build_sf_client(
        FakeSalesforce(
            {
                "records": [
                    {
                        "CommentBody": "Old public reply",
                        "CreatedDate": "2026-05-15T09:00:00Z",
                        "IsPublished": True,
                    },
                    {
                        "CommentBody": "Internal note",
                        "CreatedDate": "2026-05-15T11:00:00Z",
                        "IsPublished": False,
                    },
                    {
                        "CommentBody": "New public reply",
                        "CreatedDate": "2026-05-15T12:00:00Z",
                        "IsPublished": True,
                    },
                ]
            }
        )
    )

    replies = sf_client.get_new_customer_replies(
        "case-1",
        "2026-05-15T10:00:00Z",
    )

    assert replies == ["New public reply"]


class FakeCompletions:
    def __init__(self, content):
        self.content = content

    async def create(self, **kwargs):
        message = SimpleNamespace(content=self.content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class FakeOpenAIClient:
    def __init__(self, content):
        self.chat = SimpleNamespace(completions=FakeCompletions(content))


@pytest.mark.asyncio
async def test_classify_reply_returns_satisfied():
    result = await classify_reply(
        "thank you it worked",
        client=FakeOpenAIClient("SATISFIED"),
    )

    assert result == "SATISFIED"


@pytest.mark.asyncio
async def test_classify_reply_returns_stuck():
    result = await classify_reply(
        "this didnt work",
        client=FakeOpenAIClient("STUCK"),
    )

    assert result == "STUCK"


@pytest.mark.asyncio
async def test_classify_reply_returns_unclear():
    result = await classify_reply(
        "okay",
        client=FakeOpenAIClient("UNCLEAR"),
    )

    assert result == "UNCLEAR"


@pytest.mark.asyncio
async def test_classify_reply_returns_unclear_for_unexpected_value():
    result = await classify_reply(
        "random text",
        client=FakeOpenAIClient("MAYBE"),
    )

    assert result == "UNCLEAR"


@pytest.mark.asyncio
async def test_handle_case_reply_calls_close_case_when_satisfied(monkeypatch):
    sf_client = SimpleNamespace(
        close_case=MagicMock(return_value=True),
        create_knowledge_article=MagicMock(return_value=True),
        update_last_reply_checked=MagicMock(return_value=True),
    )
    monkeypatch.setattr(reply_handler, "classify_reply", AsyncMock(return_value="SATISFIED"))
    monkeypatch.setattr(reply_handler, "ingest_resolved_qa", AsyncMock(return_value=True))
    monkeypatch.setattr(reply_handler, "send_webex_message", AsyncMock(return_value=True))
    monkeypatch.setattr(
        reply_handler,
        "settings",
        SimpleNamespace(self_learning_enabled=True, confidence_threshold=0.6),
    )

    await reply_handler.handle_case_reply(
        {
            "case_id": "case-1",
            "case_number": "0001",
            "subject": "Router reset",
            "description": "Cannot reset",
        },
        ["thank you it worked"],
        sf_client,
        "http://testserver",
    )

    sf_client.close_case.assert_called_once_with("case-1")
    sf_client.create_knowledge_article.assert_called_once()
    sf_client.update_last_reply_checked.assert_called_once()


@pytest.mark.asyncio
async def test_handle_case_reply_calls_retrieval_and_post_answer_when_stuck(
    monkeypatch,
):
    sf_client = SimpleNamespace(
        post_answer_to_case=MagicMock(return_value=True),
        flag_for_human_review=MagicMock(return_value=True),
        update_last_reply_checked=MagicMock(return_value=True),
    )
    monkeypatch.setattr(reply_handler, "classify_reply", AsyncMock(return_value="STUCK"))
    monkeypatch.setattr(
        reply_handler,
        "call_retriever",
        AsyncMock(
            return_value={
                "data": {
                    "message": "Try rebooting the router.",
                    "info": {
                        "confidence": 0.95,
                        "sources": ["manual.pdf"],
                    },
                }
            }
        ),
    )
    monkeypatch.setattr(
        reply_handler,
        "settings",
        SimpleNamespace(self_learning_enabled=True, confidence_threshold=0.6),
    )

    await reply_handler.handle_case_reply(
        {
            "case_id": "case-1",
            "case_number": "0001",
            "subject": "Router reset",
            "description": "Cannot reset",
        },
        ["this didnt work"],
        sf_client,
        "http://testserver",
    )

    reply_handler.call_retriever.assert_awaited_once_with(
        "http://testserver",
        "case-1",
        "this didnt work",
    )
    sf_client.post_answer_to_case.assert_called_once_with(
        "case-1",
        "Try rebooting the router.",
        ["manual.pdf"],
        0.95,
    )


@pytest.mark.asyncio
async def test_handle_case_reply_sends_webex_message_when_unclear(monkeypatch):
    sf_client = SimpleNamespace(update_last_reply_checked=MagicMock(return_value=True))
    send_webex_message = AsyncMock(return_value=True)
    monkeypatch.setattr(reply_handler, "classify_reply", AsyncMock(return_value="UNCLEAR"))
    monkeypatch.setattr(reply_handler, "send_webex_message", send_webex_message)

    await reply_handler.handle_case_reply(
        {
            "case_id": "case-1",
            "case_number": "0001",
            "subject": "Router reset",
            "description": "Cannot reset",
        },
        ["not sure"],
        sf_client,
        "http://testserver",
    )

    send_webex_message.assert_awaited_once()
    assert "manual review" in send_webex_message.await_args.args[0]


@pytest.mark.asyncio
async def test_update_last_reply_checked_always_called(monkeypatch):
    sf_client = SimpleNamespace(update_last_reply_checked=MagicMock(return_value=True))
    monkeypatch.setattr(
        reply_handler,
        "classify_reply",
        AsyncMock(side_effect=RuntimeError("classifier failed")),
    )

    await reply_handler.handle_case_reply(
        {
            "case_id": "case-1",
            "case_number": "0001",
            "subject": "Router reset",
            "description": "Cannot reset",
        },
        ["unclear"],
        sf_client,
        "http://testserver",
    )

    sf_client.update_last_reply_checked.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_resolved_qa_calls_graph_writer_on_success(monkeypatch):
    writes = []

    class FakeEmbedder:
        async def embed_text(self, text):
            return [0.1] * 1536

    class FakeEntityExtractor:
        async def extract_entities(self, text):
            return {
                "products": [],
                "versions": [],
                "symptoms": [],
                "root_causes": [],
                "resolutions": [],
                "errors": [],
                "features": [],
            }

    class FakeGraphWriter:
        def write_document_graph(self, document, chunks, entities_by_chunk):
            writes.append(
                {
                    "document": document,
                    "chunks": chunks,
                    "entities_by_chunk": entities_by_chunk,
                }
            )

    monkeypatch.setattr(
        self_learner,
        "strip_pii_from_qa",
        AsyncMock(return_value="Question: [Customer] cannot reset router\n\nAnswer: It worked"),
    )
    monkeypatch.setattr(self_learner, "OpenAIEmbedder", FakeEmbedder)
    monkeypatch.setattr(self_learner, "OpenAIEntityExtractor", FakeEntityExtractor)
    monkeypatch.setattr(self_learner, "GraphWriter", FakeGraphWriter)

    result = await self_learner.ingest_resolved_qa(
        "John cannot reset router",
        "It worked",
        "0001",
    )

    assert result is True
    assert len(writes) == 1
    assert writes[0]["document"]["id"] == "resolved_case_0001"
    assert writes[0]["chunks"][0]["embedding"] == [0.1] * 1536
