# CasePilot

## PROJECT OVERVIEW

CasePilot is a FastAPI and React application that ingests support knowledge from PDFs and web pages into Neo4j. It uses OpenAI embeddings, entity extraction, graph relationships, fulltext search, and answer generation to find responses for Salesforce cases. A background Salesforce agent polls new cases, routes high-confidence answers back to Salesforce, and flags lower-confidence cases for human review. When customers confirm resolution, the app can generate a sanitized knowledge article and feed the resolved Q&A back into the knowledge graph.

## HOW IT WORKS

### Knowledge ingestion pipeline

PDF ingestion starts at `POST /upload-pdf`. The backend validates that the upload is a PDF, detects duplicate PDFs by title, stores a processing `Document` record in Neo4j, and runs ingestion in a FastAPI background task. `pdf_extractor.py` reads text with PyMuPDF, `chunker.py` splits pages into overlapping chunks, `embedder.py` creates OpenAI embeddings, `entity_extractor.py` extracts technical entities, and `graph_writer.py` writes `Document`, `Chunk`, and `Entity` nodes plus `HAS_CHUNK`, `MENTIONS`, and `RELATED_TO` relationships.

URL ingestion starts at `POST /ingest-url`. In `single` mode, the submitted page is ingested directly. In `crawl` mode, `discover_links()` fetches the start page, extracts links with BeautifulSoup, optionally filters links by URL pattern, and enforces the requested `max_pages` cap before queueing each page. Each URL page is fetched, stripped of script/style/navigation/header/footer content, chunked, embedded, entity-enriched, and written to Neo4j with processing/completed/failed status tracking.

### Case retrieval and auto-answer flow

At application startup, `main.py` creates the Neo4j vector and fulltext indexes and starts the Salesforce case polling loop. `case_listener.py` polls Salesforce for new cases where `Status = 'New'` and `CasePilot1_Processed__c = false`, builds a question from the case subject and description, and calls `POST /api/v1/retriever` with `mode=graph_vector_fulltext`. The retriever runs vector search, fulltext search, graph expansion, result combining, and OpenAI answer generation.

The returned confidence is compared with `CONFIDENCE_THRESHOLD`. High-confidence cases are posted back to Salesforce with an automated CasePilot Agent comment and moved to `In Progress`. Low-confidence cases are flagged for human review, marked high priority in Salesforce, recorded in the in-memory case store, and sent to Webex if Webex is configured.

### Reply handling and escalation

`reply_poll_loop()` polls Salesforce `In Progress` cases and reads new customer comments after `CasePilot1_LastReplyChecked_c__c`. Comments containing the CasePilot Agent marker are ignored so the system does not process its own comments as customer replies. `reply_classifier.py` uses OpenAI to classify customer replies as `SATISFIED`, `STUCK`, or `UNCLEAR`.

For `SATISFIED`, CasePilot closes the Salesforce case, updates local case status to `resolved`, optionally runs self-learning, and sends a Webex auto-close message. For `STUCK`, it flags the case for human review with confidence `0.0` and sends a Webex message that the customer is still stuck. For `UNCLEAR`, it sends a Webex message asking a human to review the case.

### Self-learning loop from resolved cases

Self-learning is controlled by `SELF_LEARNING_ENABLED`. When a satisfied reply closes a case and self-learning is enabled, `reply_handler.py` fetches the full Salesforce case comment history and `self_learner.py` asks OpenAI to write a technical KB article body from that history. It also runs PII removal on the resolved question and answer, chunks the sanitized Q&A, creates embeddings, extracts entities, and writes the result back to Neo4j as a completed `resolved_case_{case_number}` document.

The Salesforce integration also creates a draft `Knowledge__kav` article with the case subject as the title, a generated summary, and the generated KB body. If Salesforce returns an article ID, the Webex auto-close message includes a link to review the draft article in Salesforce.

## KEY FEATURES

- PDF upload ingestion with duplicate detection by PDF title.
- URL ingestion for a single page or a capped crawl with optional URL pattern filtering and required `max_pages` for crawl mode.
- Background ingestion tasks with document status tracking.
- Text chunking with a 512-token target and 64-token overlap.
- OpenAI embeddings for chunks and retrieval questions.
- Entity extraction for products, versions, symptoms, root causes, resolutions, errors, and features.
- Neo4j storage for documents, chunks, entities, embeddings, and graph relationships.
- Neo4j vector index `chunk_embedding` and fulltext index `chunk_text`.
- Triple search using vector search, fulltext search, and graph expansion.
- Retrieval modes for `vector`, `graph`, `fulltext`, and `graph_vector_fulltext`.
- Optional document-name filtering in retrieval.
- OpenAI answer generation constrained to retrieved context, with fallback behavior when the knowledge base lacks an answer.
- Confidence threshold routing for automatic Salesforce answers versus human review.
- In-memory case tracking with list, summary, resolve, and escalate endpoints.
- Salesforce integration for case polling, comments, status updates, priority updates, reply polling, auto-close, and draft Knowledge article creation.
- Webex notifications for low-confidence cases, stuck customer replies, unclear replies, and auto-closed cases.
- Reply classification for satisfied, stuck, and unclear customer responses.
- PII removal before self-learning ingestion.
- KB article generation from resolved Salesforce case history.
- React/Vite frontend for URL/PDF ingestion, document status totals, refresh, and document deletion.

## TECH STACK

### Backend

- Python 3.10+ syntax is used in the codebase.
- FastAPI `0.115.6` for API routing and lifespan startup.
- Uvicorn `0.34.0` for local ASGI serving.
- Pydantic `2.10.4` for request and response schemas.
- python-dotenv `1.0.1` for loading `.env`.
- httpx `0.28.1` for OpenAI-adjacent internal HTTP calls, Salesforce token requests, web page fetches, and Webex REST calls.
- OpenAI Python SDK `1.59.6`.
- Neo4j Python driver `5.27.0`.
- PyMuPDF `1.25.1` for PDF text extraction.
- Beautiful Soup `4.12.3` for URL HTML parsing.
- python-multipart `0.0.20` for PDF uploads.
- simple-salesforce `1.12.5` for Salesforce API access.
- pytest `8.3.4` and pytest-asyncio `0.25.0` for backend tests.

### Frontend

- React `18.3.1`.
- React DOM `18.3.1`.
- Vite `5.4.11`.
- `@vitejs/plugin-react` `4.3.4`.

### External systems

- Neo4j stores documents, chunks, entities, vector embeddings, fulltext indexes, and graph relationships.
- OpenAI provides embeddings, entity extraction, answer generation, reply classification, PII removal, and KB article generation.
- Salesforce provides case polling, comments, status updates, priority updates, reply history, and draft Knowledge articles.
- Webex receives human-review and reply-status notifications through the Webex messages API.

### OpenAI model usage

| Task | Code path | Model setting | Default model |
|---|---|---|---|
| Chunk embeddings | `backend/ingestion/embedder.py` | `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` |
| Retrieval question embeddings | `backend/retrieval/vector_searcher.py` through `OpenAIEmbedder` | `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` |
| Entity extraction | `backend/ingestion/entity_extractor.py` | `OPENAI_LLM_MODEL` | `gpt-4o` |
| Answer generation | `backend/retrieval/answer_generator.py` | `model` query parameter, defaulting to `OPENAI_LLM_MODEL` | `gpt-4o` |
| Reply classification | `backend/agents/reply_classifier.py` | `OPENAI_LLM_MODEL` | `gpt-4o` |
| PII removal | `backend/agents/self_learner.py` | `OPENAI_LLM_MODEL` | `gpt-4o` |
| KB article generation | `backend/agents/self_learner.py` | `OPENAI_LLM_MODEL` | `gpt-4o` |

## PROJECT STRUCTURE

```text
backend/
├── README.md                         # Backend-specific notes.
├── __init__.py                       # Marks backend as a Python package.
├── config.py                         # Loads environment variables into the Settings dataclass.
├── main.py                           # Creates the FastAPI app, Neo4j indexes, routers, and Salesforce polling tasks.
├── agents/
│   ├── README.md                     # Agent-specific notes.
│   ├── __init__.py                   # Marks agents as a Python package.
│   ├── agent_decision.py             # Routes high-confidence cases to auto-answer and low-confidence cases to human review.
│   ├── case_listener.py              # Polls Salesforce for new cases and in-progress replies, then calls retriever/reply handlers.
│   ├── reply_classifier.py           # Uses OpenAI to classify customer replies as SATISFIED, STUCK, or UNCLEAR.
│   ├── reply_handler.py              # Handles customer replies, auto-close, escalation notifications, and self-learning triggers.
│   └── self_learner.py               # Generates KB article bodies, strips PII, and ingests resolved Q&A into Neo4j.
├── ingestion/
│   ├── __init__.py                   # Marks ingestion as a Python package.
│   ├── chunker.py                    # Splits extracted pages into overlapping text chunks.
│   ├── embedder.py                   # Wraps OpenAI embedding calls with retry logic.
│   ├── entity_extractor.py           # Extracts technical entities from chunks with OpenAI JSON output.
│   ├── graph_writer.py               # Creates Neo4j indexes and writes/lists/deletes document graphs.
│   ├── pdf_extractor.py              # Extracts text from PDF pages with PyMuPDF.
│   └── url_extractor.py              # Fetches HTML, extracts visible text, discovers links, filters links, and caps crawl pages.
├── integrations/
│   ├── README.md                     # Integration-specific notes.
│   ├── __init__.py                   # Marks integrations as a Python package.
│   ├── salesforce_client.py          # Handles Salesforce auth, case queries, comments, status updates, replies, and Knowledge articles.
│   └── webex_client.py               # Sends Webex room notifications for human-review cases.
├── models/
│   ├── README.md                     # Model-specific notes.
│   ├── __init__.py                   # Marks models as a Python package.
│   ├── case_store.py                 # Stores processed case records in memory with summary counts.
│   └── schemas.py                    # Defines Pydantic schemas for ingestion, retrieval, and case endpoints.
├── retrieval/
│   ├── README.md                     # Retrieval-specific notes.
│   ├── __init__.py                   # Marks retrieval as a Python package.
│   ├── answer_generator.py           # Builds retrieval context and generates grounded OpenAI answers.
│   ├── fulltext_searcher.py          # Queries Neo4j fulltext index `chunk_text`.
│   ├── graph_expander.py             # Finds related chunks through `RELATED_TO` and shared entity relationships.
│   ├── result_combiner.py            # Deduplicates, ranks, truncates, and scores retrieval results.
│   └── vector_searcher.py            # Embeds questions and queries Neo4j vector index `chunk_embedding`.
├── routers/
│   ├── README.md                     # Router-specific notes.
│   ├── __init__.py                   # Marks routers as a Python package.
│   ├── cases.py                      # Exposes case list, summary, detail, resolve, and escalate endpoints.
│   ├── ingestion.py                  # Exposes PDF upload, URL ingestion, document list/delete, health, and background ingestion.
│   └── retrieval.py                  # Exposes the retriever endpoint and coordinates vector/fulltext/graph retrieval.
└── tests/
    ├── test_ingestion.py             # Tests PDF extraction, chunking, ingestion endpoints, URL filtering, and graph deletion.
    ├── test_phase3.py                # Tests Salesforce case processing and confidence routing behavior.
    ├── test_phase4.py                # Tests case store and case router behavior.
    ├── test_phase5.py                # Tests Webex notification behavior.
    ├── test_phase6.py                # Tests reply classification, reply handling, self-learning, and Salesforce reply filtering.
    └── test_retrieval.py             # Tests retrieval search, result combining, answer generation, and retrieval endpoint behavior.
```

## ENVIRONMENT VARIABLES

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | empty string | API key used by the OpenAI client for embeddings and chat completions. |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model for chunk embeddings and retrieval question embeddings. |
| `OPENAI_LLM_MODEL` | `gpt-4o` | OpenAI chat model for entity extraction, answer generation default, reply classification, PII removal, and KB article generation. |
| `NEO4J_URI` | empty string | Neo4j connection URI. Graph writes/searches are disabled if Neo4j credentials are incomplete. |
| `NEO4J_USERNAME` | `neo4j` | Neo4j username. |
| `NEO4J_PASSWORD` | empty string | Neo4j password. |
| `CONFIDENCE_THRESHOLD` | `0.6` | Minimum retrieval confidence for automatic Salesforce answers. Lower confidence routes to human review. |
| `ENVIRONMENT` | `development` | Environment label loaded into settings. |
| `SALESFORCE_CLIENT_ID` | empty string | Salesforce connected app client ID for OAuth client credentials. |
| `SALESFORCE_CLIENT_SECRET` | empty string | Salesforce connected app client secret for OAuth client credentials. |
| `SALESFORCE_INSTANCE_URL` | empty string | Base Salesforce instance URL used for OAuth, case links, and Knowledge article links. |
| `SALESFORCE_USERNAME` | empty string | Loaded into settings but not used by the current Salesforce client implementation. |
| `SALESFORCE_PASSWORD` | empty string | Loaded into settings but not used by the current Salesforce client implementation. |
| `SALESFORCE_SECURITY_TOKEN` | empty string | Loaded into settings but not used by the current Salesforce client implementation. |
| `SALESFORCE_POLL_INTERVAL` | `10` | Seconds between polls for new Salesforce cases. |
| `WEBEX_BOT_TOKEN` | empty string | Webex bot token used to post room messages. |
| `WEBEX_ROOM_ID` | empty string | Webex room ID where notifications are sent. |
| `REPLY_POLL_INTERVAL` | `60` | Seconds between polls for new replies on in-progress Salesforce cases. |
| `SELF_LEARNING_ENABLED` | `true` | Enables self-learning from satisfied/resolved cases when set to `true`. |

`embedding_dimensions` is fixed in code at `1536` and is not read from an environment variable.

## HOW TO RUN

### Prerequisites

- Python 3.10 or newer. The backend uses modern type syntax such as `str | None`.
- Node.js 18 or newer. Vite `5.4.11` declares `^18.0.0 || >=20.0.0`.
- A Neo4j database that supports vector indexes and fulltext indexes.
- An OpenAI API key.
- Salesforce and Webex credentials if you want the background agent and notifications to run.

### Backend setup

From the repository root:

```bash
cd WebApp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `WebApp/.env` and set the variables listed in the Environment Variables section. For ingestion and retrieval, the backend needs `OPENAI_API_KEY`, `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`. Salesforce polling requires the Salesforce client credentials and instance URL. Webex notifications require `WEBEX_BOT_TOKEN` and `WEBEX_ROOM_ID`.

Start the backend:

```bash
uvicorn backend.main:app --reload
```

The backend runs on `http://127.0.0.1:8000` by default. On startup it creates Neo4j vector/fulltext indexes and starts Salesforce polling tasks; if Salesforce settings or `simple-salesforce` are unavailable, polling logs a warning and stops.

### Frontend setup

In another terminal:

```bash
cd WebApp/frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5173`. The Vite dev server proxies `/upload-pdf`, `/ingest-url`, and `/documents` to `http://localhost:8000`.

### Verify it is running

Check the backend health endpoint:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

Open `http://localhost:5173` to use the ingestion and document status UI.

## API ENDPOINTS

| Method | Path | What it does |
|---|---|---|
| `POST` | `/upload-pdf` | Uploads a PDF, creates a processing document record, and ingests extracted PDF text in the background. |
| `POST` | `/ingest-url` | Ingests one URL or crawls linked URLs. Crawl mode requires `max_pages` between 1 and 500 and can use `url_pattern`. |
| `GET` | `/documents` | Lists ingested documents with source, type, status, upload timestamp, and chunk count. |
| `DELETE` | `/documents/{document_id}` | Deletes a document, its chunks, relationships, and orphaned entities from Neo4j. |
| `GET` | `/health` | Returns `{"status": "ok"}`. |
| `POST` | `/api/v1/retriever` | Retrieves chunks using `vector`, `graph`, `fulltext`, or `graph_vector_fulltext`, optionally generates an answer, and returns sources, model, node details, response time, mode, and confidence. |
| `GET` | `/cases` | Lists in-memory processed case records and sets summary counts in response headers. |
| `GET` | `/cases/summary` | Returns total, auto-answered, flagged, resolved, and escalated case counts from the in-memory case store. |
| `GET` | `/cases/{case_id}` | Returns one in-memory case record or 404 if it is not found. |
| `POST` | `/cases/{case_id}/resolve` | Marks a case record resolved locally and attempts to close the Salesforce case. |
| `POST` | `/cases/{case_id}/escalate` | Marks a case record escalated locally and attempts to set Salesforce priority high with an internal comment. |

`/api/v1/retriever` accepts query parameters `question`, `session_id`, `mode`, `response_type`, `document_names`, `top_k`, and `model`, plus a required form field named `database`.
