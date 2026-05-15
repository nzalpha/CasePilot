from typing import Literal, Optional

from pydantic import BaseModel


class IngestUrlRequest(BaseModel):
    url: str
    crawl_mode: Literal["single", "crawl"] = "single"
    url_pattern: Optional[str] = None


class DocumentResponse(BaseModel):
    document_id: str
    title: str
    source: str
    source_type: Literal["pdf", "url"]
    status: Literal["processing", "completed", "failed", "duplicate"]
    uploaded_at: str
    chunk_count: Optional[int] = None


class IngestionResponse(BaseModel):
    document_id: str
    status: str
    message: str


class UrlIngestionResponse(BaseModel):
    document_ids: list[str]
    status: str
    message: str


class DeleteResponse(BaseModel):
    document_id: str
    deleted_chunks: int
    deleted_entities: int
    message: str


class ChunkResult(BaseModel):
    chunk_id: str
    text: str
    score: float
    doc_link: str
    page_number: int
    document_id: str


class RetrievalInfo(BaseModel):
    sources: list[str]
    model: str
    nodedetails: dict
    response_time: float
    mode: str
    confidence: float


class RetrievalData(BaseModel):
    session_id: str
    message: Optional[str]
    info: RetrievalInfo


class RetrievalResponse(BaseModel):
    status: str
    data: RetrievalData
