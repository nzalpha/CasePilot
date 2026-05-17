from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class IngestUrlRequest(BaseModel):
    url: str
    crawl_mode: Literal["single", "crawl"] = "single"
    url_pattern: Optional[str] = None
    max_pages: Optional[int] = Field(default=None, ge=1, le=500)

    @model_validator(mode="after")
    def max_pages_required_for_crawl(self) -> "IngestUrlRequest":
        if self.crawl_mode == "crawl" and self.max_pages is None:
            raise ValueError("max_pages is required when crawl_mode is 'crawl'")
        return self


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


class CaseResponse(BaseModel):
    case_id: str
    case_number: str
    subject: str
    question: str
    action: str
    confidence: float
    answer: Optional[str]
    sources: list[str]
    processed_at: str
    status: str


class CaseSummaryResponse(BaseModel):
    total: int
    auto_answered: int
    flagged_for_human: int
    resolved: int
    escalated: int


class CaseActionResponse(BaseModel):
    case_id: str
    status: str
    message: str
