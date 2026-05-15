from __future__ import annotations

from backend.models.schemas import ChunkResult


async def combine_results(
    vector_results: list[ChunkResult] | None = None,
    graph_results: list[ChunkResult] | None = None,
    fulltext_results: list[ChunkResult] | None = None,
    top_k: int = 10,
) -> tuple[list[ChunkResult], float]:
    vector_results = vector_results or []
    result_groups = [
        vector_results,
        graph_results or [],
        fulltext_results or [],
    ]
    combined: dict[str, ChunkResult] = {}

    for results in result_groups:
        for chunk in results:
            existing = combined.get(chunk.chunk_id)
            if existing is None or chunk.score > existing.score:
                combined[chunk.chunk_id] = chunk

    ranked_results = sorted(
        combined.values(),
        key=lambda chunk: chunk.score,
        reverse=True,
    )
    confidence = max((chunk.score for chunk in vector_results), default=0.0)
    return ranked_results[:top_k], confidence
