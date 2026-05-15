import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.models.schemas import ChunkResult
from backend.retrieval.answer_generator import FALLBACK_ANSWER, generate_answer
from backend.retrieval.graph_expander import GraphExpander
from backend.retrieval.result_combiner import combine_results
from backend.retrieval.vector_searcher import VectorSearcher
import backend.routers.retrieval as retrieval_router_module


class FakeResult:
    def __init__(self, records):
        self.records = records

    def __iter__(self):
        return iter(self.records)


class FakeSession:
    def __init__(self, records, records_by_chunk_id=None):
        self.records = records
        self.records_by_chunk_id = records_by_chunk_id or {}
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def run(self, query, **params):
        self.calls.append({"query": query, "params": params})
        if "chunk_id" in params:
            return FakeResult(self.records_by_chunk_id.get(params["chunk_id"], []))
        return FakeResult(self.records)


class FakeDriver:
    def __init__(self, records=None, records_by_chunk_id=None):
        self.session_instance = FakeSession(
            records or [],
            records_by_chunk_id=records_by_chunk_id,
        )

    def session(self):
        return self.session_instance


class FakeEmbedder:
    async def embed_text(self, text):
        return [0.1] * 1536


def chunk(chunk_id, score, document_id="doc-1", doc_link="source.pdf"):
    return ChunkResult(
        chunk_id=chunk_id,
        text=f"Text for {chunk_id}",
        score=score,
        doc_link=doc_link,
        page_number=1,
        document_id=document_id,
    )


@pytest.mark.asyncio
async def test_vector_search_returns_chunks():
    driver = FakeDriver(
        records=[
            {
                "chunk_id": "chunk-1",
                "text": "Router X200 timeout fix",
                "doc_link": "manual.pdf",
                "page_number": 3,
                "document_id": "doc-1",
                "score": 0.91,
            }
        ]
    )
    searcher = VectorSearcher(driver=driver, embedder=FakeEmbedder())

    results = await searcher.search("How do I fix timeout?", top_k=5)

    assert results == [
        ChunkResult(
            chunk_id="chunk-1",
            text="Router X200 timeout fix",
            score=0.91,
            doc_link="manual.pdf",
            page_number=3,
            document_id="doc-1",
        )
    ]
    assert driver.session_instance.calls[0]["params"]["top_k"] == 5
    assert len(driver.session_instance.calls[0]["params"]["embedding"]) == 1536


@pytest.mark.asyncio
async def test_graph_expander_follows_edges():
    driver = FakeDriver(
        records_by_chunk_id={
            "chunk-1": [
                {
                    "chunk_id": "chunk-1",
                    "text": "Original chunk",
                    "doc_link": "manual.pdf",
                    "page_number": 1,
                    "document_id": "doc-1",
                },
                {
                    "chunk_id": "chunk-2",
                    "text": "Related chunk",
                    "doc_link": "manual.pdf",
                    "page_number": 2,
                    "document_id": "doc-1",
                },
            ]
        }
    )
    expander = GraphExpander(driver)

    results = await expander.expand([chunk("chunk-1", 0.87)])

    assert results == [
        ChunkResult(
            chunk_id="chunk-2",
            text="Related chunk",
            score=0.0,
            doc_link="manual.pdf",
            page_number=2,
            document_id="doc-1",
        )
    ]


@pytest.mark.asyncio
async def test_result_combiner_deduplicates():
    results, confidence = await combine_results(
        vector_results=[chunk("chunk-1", 0.5), chunk("chunk-2", 0.2)],
        fulltext_results=[chunk("chunk-1", 0.9), chunk("chunk-3", 0.3)],
        top_k=10,
    )

    assert [result.chunk_id for result in results] == [
        "chunk-1",
        "chunk-3",
        "chunk-2",
    ]
    assert results[0].score == 0.9
    assert confidence == 0.5


@pytest.mark.asyncio
async def test_answer_generator_empty_chunks_returns_fallback():
    result = await generate_answer(
        question="How do I fix timeout?",
        chunks=[],
        model="gpt-4o",
    )

    assert result == {
        "answer": FALLBACK_ANSWER,
        "confidence": 0.0,
        "sources": [],
    }


@pytest.mark.asyncio
async def test_retrieval_endpoint_combined_mode(monkeypatch):
    class FakeVectorSearcher:
        def __init__(self, driver):
            self.driver = driver

        async def search(self, question, top_k=5):
            return [chunk("chunk-1", 0.87, doc_link="manual.pdf")]

    class FakeFulltextSearcher:
        def __init__(self, driver):
            self.driver = driver

        async def search(self, question, top_k=5):
            return [
                chunk("chunk-1", 0.42, doc_link="manual.pdf"),
                chunk("chunk-2", 0.4, doc_link="kb.html"),
            ]

    class FakeGraphExpander:
        def __init__(self, driver):
            self.driver = driver

        async def expand(self, chunks):
            return [chunk("chunk-3", 0.0, doc_link="related.pdf")]

    async def fake_generate_answer(question, chunks, model, confidence):
        return {
            "answer": "Restart the router and apply the timeout fix.",
            "confidence": confidence,
            "sources": ["manual.pdf", "kb.html", "related.pdf"],
        }

    monkeypatch.setattr(
        retrieval_router_module,
        "VectorSearcher",
        FakeVectorSearcher,
    )
    monkeypatch.setattr(
        retrieval_router_module,
        "FulltextSearcher",
        FakeFulltextSearcher,
    )
    monkeypatch.setattr(
        retrieval_router_module,
        "GraphExpander",
        FakeGraphExpander,
    )
    monkeypatch.setattr(
        retrieval_router_module,
        "generate_answer",
        fake_generate_answer,
    )

    app = FastAPI()
    app.state.graph_writer = SimpleNamespace(driver=object())
    app.include_router(retrieval_router_module.router)
    client = TestClient(app)

    response = client.post(
        "/api/v1/retriever",
        params={
            "question": "How do I fix timeout?",
            "session_id": "session-123",
            "mode": "graph_vector_fulltext",
            "model": "gpt-4o",
        },
        data={"database": "neo4j"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "Success"
    assert payload["data"]["session_id"] == "session-123"
    assert payload["data"]["message"] == "Restart the router and apply the timeout fix."
    info = payload["data"]["info"]
    assert info["sources"] == ["manual.pdf", "kb.html", "related.pdf"]
    assert info["model"] == "gpt-4o"
    assert info["mode"] == "graph_vector_fulltext"
    assert info["confidence"] == 0.87
    assert info["nodedetails"]["chunkdetails"] == [
        {"id": "chunk-1", "score": 0.87},
        {"id": "chunk-2", "score": 0.4},
        {"id": "chunk-3", "score": 0.0},
    ]
    assert isinstance(info["response_time"], float)
