from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from fastapi import APIRouter, Form, HTTPException, Query, Request
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from backend.config import settings
from backend.models.schemas import ChunkResult, RetrievalResponse
from backend.retrieval.answer_generator import generate_answer, unique_sources
from backend.retrieval.fulltext_searcher import FulltextSearcher
from backend.retrieval.graph_expander import GraphExpander
from backend.retrieval.result_combiner import combine_results
from backend.retrieval.vector_searcher import VectorSearcher


logger = logging.getLogger(__name__)
router = APIRouter()

VALID_MODES = {"vector", "graph", "fulltext", "graph_vector_fulltext"}
VALID_RESPONSE_TYPES = {"answer", "retrieval_only"}


def chunk_summary(chunk: ChunkResult) -> dict[str, Any]:
    return {
        "id": chunk.chunk_id,
        "score": chunk.score,
    }


def chunk_details(chunk: ChunkResult) -> dict[str, Any]:
    return {
        "id": chunk.chunk_id,
        "text": chunk.text,
        "score": chunk.score,
        "doc_link": chunk.doc_link,
        "page_number": chunk.page_number,
        "document_id": chunk.document_id,
    }


def parse_document_names(document_names: str | None) -> set[str]:
    if not document_names:
        return set()
    return {name.strip() for name in document_names.split(",") if name.strip()}


async def filter_result_groups_by_document_names(
    driver: Any,
    result_groups: list[list[ChunkResult]],
    document_names: str | None,
) -> list[list[ChunkResult]]:
    allowed_titles = parse_document_names(document_names)
    if not allowed_titles:
        return result_groups

    document_ids = sorted(
        {
            chunk.document_id
            for results in result_groups
            for chunk in results
            if chunk.document_id
        }
    )
    if not document_ids:
        return [[] for _results in result_groups]

    query = """
    MATCH (d:Document)
    WHERE d.id IN $document_ids
    RETURN d.id AS document_id,
           d.title AS title
    """
    try:
        with driver.session() as session:
            records = session.run(query, document_ids=document_ids)
            titles_by_document_id = {
                record["document_id"]: record["title"] for record in records
            }
    except (Neo4jError, ServiceUnavailable) as exc:
        logger.exception("Document title lookup failed: %s", exc)
        raise

    return [
        [
            chunk
            for chunk in results
            if titles_by_document_id.get(chunk.document_id) in allowed_titles
        ]
        for results in result_groups
    ]


async def retrieve_chunks(
    driver: Any,
    question: str,
    mode: str,
    top_k: int,
    document_names: str | None,
) -> tuple[list[ChunkResult], float]:
    vector_searcher = VectorSearcher(driver)
    fulltext_searcher = FulltextSearcher(driver)
    graph_expander = GraphExpander(driver)

    if mode == "vector":
        vector_results = await vector_searcher.search(question, top_k=top_k)
        [vector_results] = await filter_result_groups_by_document_names(
            driver, [vector_results], document_names
        )
        return await combine_results(vector_results=vector_results, top_k=top_k)

    if mode == "graph":
        vector_results = await vector_searcher.search(question, top_k=top_k)
        graph_results = await graph_expander.expand(vector_results)
        vector_results, graph_results = await filter_result_groups_by_document_names(
            driver, [vector_results, graph_results], document_names
        )
        return await combine_results(
            vector_results=vector_results,
            graph_results=graph_results,
            top_k=top_k,
        )

    if mode == "fulltext":
        fulltext_results = await fulltext_searcher.search(question, top_k=top_k)
        [fulltext_results] = await filter_result_groups_by_document_names(
            driver, [fulltext_results], document_names
        )
        return await combine_results(fulltext_results=fulltext_results, top_k=top_k)

    vector_results, fulltext_results = await asyncio.gather(
        vector_searcher.search(question, top_k=top_k),
        fulltext_searcher.search(question, top_k=top_k),
    )
    seed_results, _confidence = await combine_results(
        vector_results=vector_results,
        fulltext_results=fulltext_results,
        top_k=top_k,
    )
    graph_results = await graph_expander.expand(seed_results)
    vector_results, fulltext_results, graph_results = (
        await filter_result_groups_by_document_names(
            driver,
            [vector_results, fulltext_results, graph_results],
            document_names,
        )
    )
    return await combine_results(
        vector_results=vector_results,
        fulltext_results=fulltext_results,
        graph_results=graph_results,
        top_k=top_k,
    )


@router.post("/api/v1/retriever", response_model=RetrievalResponse)
async def retrieve(
    request: Request,
    question: str = Query(...),
    session_id: str = Query(...),
    mode: str = Query("graph_vector_fulltext"),
    response_type: str = Query("answer"),
    document_names: Optional[str] = Query(None),
    top_k: int = Query(5, ge=1),
    model: str = Query(settings.openai_llm_model),
    database: str = Form(...),
) -> RetrievalResponse:
    if mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail="Invalid retrieval mode")
    if response_type not in VALID_RESPONSE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid response_type")

    graph_writer = getattr(request.app.state, "graph_writer", None)
    driver = getattr(graph_writer, "driver", None)
    if driver is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    logger.info("Retriever database parameter received: %s", database)
    start_time = time.perf_counter()

    chunks, confidence = await retrieve_chunks(
        driver=driver,
        question=question,
        mode=mode,
        top_k=top_k,
        document_names=document_names,
    )

    if response_type == "retrieval_only":
        message = None
        sources = unique_sources(chunks)
        node_details = {"chunkdetails": [chunk_details(chunk) for chunk in chunks]}
    else:
        answer_result = await generate_answer(
            question=question,
            chunks=chunks,
            model=model,
            confidence=confidence,
        )
        message = answer_result["answer"]
        sources = answer_result["sources"]
        confidence = answer_result["confidence"]
        node_details = {"chunkdetails": [chunk_summary(chunk) for chunk in chunks]}

    response_time = round(time.perf_counter() - start_time, 4)
    return RetrievalResponse(
        status="Success",
        data={
            "session_id": session_id,
            "message": message,
            "info": {
                "sources": sources,
                "model": model,
                "nodedetails": node_details,
                "response_time": response_time,
                "mode": mode,
                "confidence": confidence,
            },
        },
    )
