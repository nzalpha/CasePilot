import sys
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.ingestion.chunker import approximate_token_count, chunk_pages
from backend.ingestion.entity_extractor import OpenAIEntityExtractor
from backend.ingestion.graph_writer import GraphWriter
from backend.ingestion.pdf_extractor import extract_pdf_pages
from backend.ingestion import url_extractor
from backend.ingestion.url_extractor import discover_links, filter_links_by_pattern
from backend.models.schemas import IngestUrlRequest
from backend.routers.ingestion import router


def test_pdf_extraction(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    document = fitz.open()
    page_one = document.new_page()
    page_one.insert_text((72, 72), "First page content")
    page_two = document.new_page()
    page_two.insert_text((72, 72), "Second page content")
    document.save(pdf_path)
    document.close()

    pages = extract_pdf_pages(pdf_path)

    assert pages == [
        {"page_number": 1, "text": "First page content"},
        {"page_number": 2, "text": "Second page content"},
    ]


def test_chunker():
    words = [f"word{i}" for i in range(900)]
    pages = [{"page_number": 1, "text": " ".join(words)}]

    chunks = chunk_pages(pages, document_id="doc")

    assert len(chunks) > 1
    assert all(approximate_token_count(chunk["text"]) <= 512 for chunk in chunks)

    first_words = chunks[0]["text"].split()
    second_words = chunks[1]["text"].split()
    assert first_words[-48:] == second_words[:48]
    assert chunks[0]["chunk_id"] == "doc_chunk_0"
    assert chunks[1]["chunk_id"] == "doc_chunk_1"


class FakeCompletions:
    async def create(self, **kwargs):
        content = """
        {
          "products": ["Router X200"],
          "versions": ["v2.1"],
          "symptoms": ["packet loss"],
          "root_causes": ["misconfigured QoS"],
          "resolutions": ["reset QoS policy"],
          "errors": ["ERR_QOS_17"],
          "features": ["traffic shaping"]
        }
        """
        message = SimpleNamespace(content=content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class FakeChat:
    def __init__(self):
        self.completions = FakeCompletions()


class FakeOpenAIClient:
    def __init__(self):
        self.chat = FakeChat()


@pytest.mark.asyncio
async def test_entity_extraction():
    extractor = OpenAIEntityExtractor(client=FakeOpenAIClient(), model="gpt-4o")

    entities = await extractor.extract_entities("Router X200 v2.1 has packet loss.")

    assert entities == {
        "products": ["Router X200"],
        "versions": ["v2.1"],
        "symptoms": ["packet loss"],
        "root_causes": ["misconfigured QoS"],
        "resolutions": ["reset QoS policy"],
        "errors": ["ERR_QOS_17"],
        "features": ["traffic shaping"],
    }


class FakeGraphWriter:
    def __init__(self, delete_result=None):
        self.delete_result = delete_result

    def get_document_by_source(self, source):
        if source == "https://example.com/doc":
            return {
                "document_id": "url-existing",
                "title": "doc",
                "source": source,
                "source_type": "url",
                "status": "completed",
                "uploaded_at": "2026-01-01T00:00:00+00:00",
            }
        return None

    def delete_document(self, document_id):
        return self.delete_result


class RecordingGraphWriter:
    def __init__(self):
        self.merged_sources = []

    def get_document_by_source(self, source):
        return None

    def merge_document(
        self,
        document_id,
        title,
        source,
        source_type,
        status,
        uploaded_at,
    ):
        self.merged_sources.append(source)


def test_duplicate_url_detection():
    app = FastAPI()
    app.state.graph_writer = FakeGraphWriter()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/ingest-url",
        json={"url": "https://example.com/doc", "crawl_mode": "single"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "duplicate"
    assert response.json()["document_ids"] == ["url-existing"]


def test_crawl_url_endpoint_caps_queued_urls(monkeypatch):
    calls = []

    async def fake_discover_links(url, url_pattern, max_pages):
        calls.append(
            {
                "url": url,
                "url_pattern": url_pattern,
                "max_pages": max_pages,
            }
        )
        return [
            "https://example.com/docs/one",
            "https://example.com/docs/two",
            "https://example.com/docs/three",
        ]

    async def fake_ingest_url_background(graph_writer, url, document):
        return None

    monkeypatch.setattr(
        "backend.routers.ingestion.discover_links",
        fake_discover_links,
    )
    monkeypatch.setattr(
        "backend.routers.ingestion.ingest_url_background",
        fake_ingest_url_background,
    )

    app = FastAPI()
    graph_writer = RecordingGraphWriter()
    app.state.graph_writer = graph_writer
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/ingest-url",
        json={
            "url": "https://example.com/docs",
            "crawl_mode": "crawl",
            "url_pattern": "/docs/",
            "max_pages": 2,
        },
    )

    assert response.status_code == 200
    assert calls == [
        {
            "url": "https://example.com/docs",
            "url_pattern": "/docs/",
            "max_pages": 2,
        }
    ]
    assert response.json()["status"] == "processing"
    assert len(response.json()["document_ids"]) == 2
    assert response.json()["message"] == (
        "URL ingestion has started for 2 page(s) (limit: 2)"
    )
    assert graph_writer.merged_sources == [
        "https://example.com/docs/one",
        "https://example.com/docs/two",
    ]


def test_crawl_request_requires_max_pages():
    with pytest.raises(ValidationError, match="max_pages is required"):
        IngestUrlRequest(url="https://example.com", crawl_mode="crawl")


def test_single_page_request_does_not_require_max_pages():
    payload = IngestUrlRequest(url="https://example.com", crawl_mode="single")

    assert payload.max_pages is None


def test_url_pattern_filter():
    links = [
        "https://example.com/docs/router-x200",
        "https://example.com/blog/router-x200",
        "https://example.com/docs/switch-a10",
    ]

    filtered = filter_links_by_pattern(links, "/docs/")

    assert filtered == [
        "https://example.com/docs/router-x200",
        "https://example.com/docs/switch-a10",
    ]


@pytest.mark.asyncio
async def test_discover_links_enforces_max_pages(monkeypatch):
    async def fake_fetch_html(url):
        return """
        <a href="/docs/one">One</a>
        <a href="/docs/two">Two</a>
        <a href="/docs/three">Three</a>
        """

    monkeypatch.setattr(url_extractor, "fetch_html", fake_fetch_html)

    links = await discover_links("https://example.com", "/docs/", max_pages=2)

    assert links == [
        "https://example.com/docs/one",
        "https://example.com/docs/two",
    ]


def test_delete_endpoint_successful_returns_counts():
    app = FastAPI()
    app.state.graph_writer = FakeGraphWriter(
        delete_result={"deleted_chunks": 2, "deleted_entities": 1}
    )
    app.include_router(router)
    client = TestClient(app)

    response = client.delete("/documents/doc-1")

    assert response.status_code == 200
    assert response.json() == {
        "document_id": "doc-1",
        "deleted_chunks": 2,
        "deleted_entities": 1,
        "message": "Document doc-1 deleted successfully",
    }


def test_delete_endpoint_missing_document_returns_404():
    app = FastAPI()
    app.state.graph_writer = FakeGraphWriter(delete_result=None)
    app.include_router(router)
    client = TestClient(app)

    response = client.delete("/documents/missing-doc")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}


class FakeResult:
    def __init__(self, record):
        self.record = record

    def single(self):
        return self.record


class InMemoryDeleteTx:
    def __init__(self, docs, document_chunks, mentions, entities, related=None):
        self.docs = docs
        self.document_chunks = document_chunks
        self.mentions = mentions
        self.entities = entities
        self.related = related or set()

    def run(self, query, **params):
        document_id = params.get("document_id")

        if "RETURN d.id AS id" in query:
            record = {"id": document_id} if document_id in self.docs else None
            return FakeResult(record)

        if "RETURN count(DISTINCT c) AS deleted_chunks" in query:
            chunks = self.document_chunks.get(document_id, set())
            return FakeResult({"deleted_chunks": len(chunks)})

        if "RETURN collect(DISTINCT e.id) AS entity_ids" in query:
            entity_ids = set()
            for chunk_id in self.document_chunks.get(document_id, set()):
                entity_ids.update(self.mentions.get(chunk_id, set()))
            return FakeResult({"entity_ids": list(entity_ids)})

        if "FOREACH (chunk IN chunks | DELETE chunk)" in query:
            chunks = set(self.document_chunks.pop(document_id, set()))
            for chunk_id in chunks:
                self.mentions.pop(chunk_id, None)
            self.related = {
                relationship
                for relationship in self.related
                if not relationship.intersection(chunks)
            }
            return FakeResult(None)

        if "RETURN deleted_entities" in query:
            entity_ids = params.get("entity_ids", [])
            referenced_entities = set()
            for chunk_entities in self.mentions.values():
                referenced_entities.update(chunk_entities)

            orphan_entities = [
                entity_id
                for entity_id in entity_ids
                if entity_id not in referenced_entities
            ]
            for entity_id in orphan_entities:
                self.entities.discard(entity_id)
            return FakeResult({"deleted_entities": len(orphan_entities)})

        if "DELETE d" in query:
            self.docs.discard(document_id)
            return FakeResult(None)

        raise AssertionError(f"Unexpected query: {query}")


class FakeSession:
    def __init__(self, tx):
        self.tx = tx

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute_write(self, callback, *args):
        return callback(self.tx, *args)


class FakeDriver:
    def __init__(self, tx):
        self.tx = tx

    def session(self):
        return FakeSession(self.tx)


def build_graph_writer(tx):
    writer = object.__new__(GraphWriter)
    writer.driver = FakeDriver(tx)
    return writer


def test_delete_document_successful_returns_counts():
    tx = InMemoryDeleteTx(
        docs={"doc-1"},
        document_chunks={"doc-1": {"chunk-1", "chunk-2"}},
        mentions={
            "chunk-1": {"router-x200"},
            "chunk-2": {"err-timeout"},
        },
        entities={"router-x200", "err-timeout"},
    )
    writer = build_graph_writer(tx)

    result = writer.delete_document("doc-1")

    assert result == {"deleted_chunks": 2, "deleted_entities": 2}
    assert "doc-1" not in tx.docs
    assert "chunk-1" not in tx.mentions
    assert "chunk-2" not in tx.mentions
    assert tx.entities == set()


def test_delete_document_missing_returns_none():
    tx = InMemoryDeleteTx(
        docs=set(),
        document_chunks={},
        mentions={},
        entities=set(),
    )
    writer = build_graph_writer(tx)

    result = writer.delete_document("missing-doc")

    assert result is None


def test_delete_document_deletes_orphaned_entities_not_shared():
    tx = InMemoryDeleteTx(
        docs={"doc-1", "doc-2"},
        document_chunks={
            "doc-1": {"chunk-1", "chunk-2"},
            "doc-2": {"chunk-3"},
        },
        mentions={
            "chunk-1": {"router-x200", "err-timeout"},
            "chunk-2": {"router-x200"},
            "chunk-3": {"router-x200"},
        },
        entities={"router-x200", "err-timeout"},
        related={frozenset({"chunk-1", "chunk-2"}), frozenset({"chunk-2", "chunk-3"})},
    )
    writer = build_graph_writer(tx)

    result = writer.delete_document("doc-1")

    assert result == {"deleted_chunks": 2, "deleted_entities": 1}
    assert "err-timeout" not in tx.entities
    assert "router-x200" in tx.entities
    assert tx.mentions == {"chunk-3": {"router-x200"}}
    assert tx.related == set()
