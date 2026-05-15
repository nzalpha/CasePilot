"""
# CasePilot Phase 1 Backend

Run the API locally:

1. Create and activate a virtual environment.
2. Install dependencies:
   `pip install -r requirements.txt`
3. Create a `.env` file with:
   `OPENAI_API_KEY`, `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`.
4. Start the server from the `WebApp` directory:
   `uvicorn backend.main:app --reload`

The server exposes:
- `POST /upload-pdf`
- `POST /ingest-url`
- `GET /documents`
- `GET /health`
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.ingestion.graph_writer import GraphWriter
from backend.routers.cases import router as cases_router
from backend.routers.ingestion import router as ingestion_router
from backend.routers.retrieval import router as retrieval_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    graph_writer = GraphWriter()
    graph_writer.create_vector_index()
    graph_writer.create_fulltext_index()
    from backend.agents.case_listener import start_poll_loop

    retrieval_base_url = "http://127.0.0.1:8000"
    poll_task = await start_poll_loop(retrieval_base_url)
    app.state.graph_writer = graph_writer
    try:
        yield
    finally:
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass
        graph_writer.close()


app = FastAPI(
    title="CasePilot Backend",
    description="Phase 1 ingestion pipeline for PDF and URL knowledge sources.",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(ingestion_router)
app.include_router(retrieval_router)
app.include_router(cases_router)
