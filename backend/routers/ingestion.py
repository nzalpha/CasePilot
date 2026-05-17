import asyncio
import hashlib
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile

from backend.ingestion.chunker import chunk_pages
from backend.ingestion.embedder import OpenAIEmbedder
from backend.ingestion.entity_extractor import OpenAIEntityExtractor
from backend.ingestion.graph_writer import GraphWriter, slugify
from backend.ingestion.pdf_extractor import extract_pdf_pages
from backend.ingestion.url_extractor import discover_links, extract_url_pages
from backend.models.schemas import (
    DeleteResponse,
    DocumentResponse,
    IngestionResponse,
    IngestUrlRequest,
    UrlIngestionResponse,
)


logger = logging.getLogger(__name__)
router = APIRouter()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def pdf_document_id(title: str) -> str:
    return slugify(title)


def url_document_id(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return f"url-{digest}"


def title_from_url(url: str) -> str:
    parsed = urlparse(url)
    path_title = parsed.path.rstrip("/").split("/")[-1]
    return path_title or parsed.netloc or url


def get_graph_writer(request: Request) -> GraphWriter:
    return request.app.state.graph_writer


async def enrich_chunks(
    chunks: list[dict],
    embedder: OpenAIEmbedder,
    entity_extractor: OpenAIEntityExtractor,
) -> tuple[list[dict], dict[str, dict]]:
    async def enrich_chunk(chunk: dict) -> tuple[dict, dict]:
        embedding_task = asyncio.create_task(embedder.embed_text(chunk["text"]))
        entities_task = asyncio.create_task(entity_extractor.extract_entities(chunk["text"]))
        embedding, entities = await asyncio.gather(embedding_task, entities_task)
        enriched = dict(chunk)
        enriched["embedding"] = embedding
        return enriched, entities

    results = await asyncio.gather(*(enrich_chunk(chunk) for chunk in chunks))
    enriched_chunks = [chunk for chunk, _entities in results]
    entities_by_chunk = {
        chunk["chunk_id"]: entities for chunk, entities in results
    }
    return enriched_chunks, entities_by_chunk


async def ingest_pages(
    graph_writer: GraphWriter,
    document: dict,
    pages: list[dict],
) -> None:
    try:
        chunks = chunk_pages(pages, document_id=document["id"])
        if not chunks:
            raise ValueError("No text chunks were produced for this document")

        embedder = OpenAIEmbedder()
        entity_extractor = OpenAIEntityExtractor()
        enriched_chunks, entities_by_chunk = await enrich_chunks(
            chunks,
            embedder,
            entity_extractor,
        )
        graph_writer.write_document_graph(document, enriched_chunks, entities_by_chunk)
        graph_writer.update_document_status(document["id"], "completed")
    except Exception as exc:
        logger.exception("Ingestion failed for document %s: %s", document["id"], exc)
        graph_writer.update_document_status(document["id"], "failed")


async def ingest_pdf_background(
    graph_writer: GraphWriter,
    file_path: str,
    document: dict,
) -> None:
    try:
        pages = extract_pdf_pages(file_path)
        await ingest_pages(graph_writer, document, pages)
    finally:
        try:
            Path(file_path).unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Failed to remove temporary PDF %s: %s", file_path, exc)


async def ingest_url_background(
    graph_writer: GraphWriter,
    url: str,
    document: dict,
) -> None:
    try:
        pages = await extract_url_pages(url)
        await ingest_pages(graph_writer, document, pages)
    except Exception as exc:
        logger.exception("URL extraction failed for %s: %s", url, exc)
        graph_writer.update_document_status(document["id"], "failed")


def create_document_record(
    document_id: str,
    title: str,
    source: str,
    source_type: str,
) -> dict:
    return {
        "id": document_id,
        "title": title,
        "source": source,
        "source_type": source_type,
        "uploaded_at": utc_now_iso(),
        "status": "processing",
    }


@router.post("/upload-pdf", response_model=IngestionResponse)
async def upload_pdf(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> IngestionResponse:
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf") or file.content_type not in {
        "application/pdf",
        "application/octet-stream",
    }:
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

    graph_writer = get_graph_writer(request)
    title = Path(filename).stem
    existing = graph_writer.get_document_by_title(title)
    if existing:
        return IngestionResponse(
            document_id=existing["document_id"],
            status="duplicate",
            message="A PDF with this title has already been ingested",
        )

    document_id = pdf_document_id(title)
    temp_path = Path(tempfile.gettempdir()) / f"{document_id}-{hashlib.md5(filename.encode()).hexdigest()}.pdf"
    content = await file.read()
    temp_path.write_bytes(content)

    document = create_document_record(
        document_id=document_id,
        title=title,
        source=filename,
        source_type="pdf",
    )
    graph_writer.merge_document(
        document_id=document["id"],
        title=document["title"],
        source=document["source"],
        source_type=document["source_type"],
        status=document["status"],
        uploaded_at=document["uploaded_at"],
    )
    background_tasks.add_task(ingest_pdf_background, graph_writer, str(temp_path), document)

    return IngestionResponse(
        document_id=document_id,
        status="processing",
        message="PDF ingestion has started",
    )


@router.post("/ingest-url", response_model=UrlIngestionResponse)
async def ingest_url(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: IngestUrlRequest,
) -> UrlIngestionResponse:
    graph_writer = get_graph_writer(request)

    if payload.crawl_mode == "single":
        existing = graph_writer.get_document_by_source(payload.url)
        if existing:
            return UrlIngestionResponse(
                document_ids=[existing["document_id"]],
                status="duplicate",
                message="This URL has already been ingested",
            )
        urls_to_ingest = [payload.url]
    else:
        max_pages = payload.max_pages or 50
        try:
            discovered_urls = await discover_links(
                payload.url,
                payload.url_pattern,
                max_pages=max_pages,
            )
        except Exception as exc:
            logger.exception("Failed to discover links from %s: %s", payload.url, exc)
            raise HTTPException(status_code=400, detail="Unable to crawl the provided URL") from exc
        urls_to_ingest = discovered_urls[:max_pages]

    document_ids: list[str] = []
    duplicate_ids: list[str] = []
    for url in urls_to_ingest:
        existing = graph_writer.get_document_by_source(url)
        if existing:
            duplicate_ids.append(existing["document_id"])
            continue

        document_id = url_document_id(url)
        document = create_document_record(
            document_id=document_id,
            title=title_from_url(url),
            source=url,
            source_type="url",
        )
        graph_writer.merge_document(
            document_id=document["id"],
            title=document["title"],
            source=document["source"],
            source_type=document["source_type"],
            status=document["status"],
            uploaded_at=document["uploaded_at"],
        )
        background_tasks.add_task(ingest_url_background, graph_writer, url, document)
        document_ids.append(document_id)

    if not document_ids and duplicate_ids:
        return UrlIngestionResponse(
            document_ids=duplicate_ids,
            status="duplicate",
            message="All requested URLs have already been ingested",
        )

    return UrlIngestionResponse(
        document_ids=document_ids,
        status="processing",
        message=(
            f"URL ingestion has started for {len(document_ids)} page(s)"
            + (
                f" (limit: {payload.max_pages})"
                if payload.crawl_mode == "crawl"
                else ""
            )
        ),
    )


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(request: Request) -> list[DocumentResponse]:
    graph_writer = get_graph_writer(request)
    return [DocumentResponse(**document) for document in graph_writer.list_documents()]


@router.delete("/documents/{document_id}", response_model=DeleteResponse)
async def delete_document(request: Request, document_id: str) -> DeleteResponse:
    graph_writer = get_graph_writer(request)
    result = graph_writer.delete_document(document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return DeleteResponse(
        document_id=document_id,
        deleted_chunks=result["deleted_chunks"],
        deleted_entities=result["deleted_entities"],
        message=f"Document {document_id} deleted successfully",
    )


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
