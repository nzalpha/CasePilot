# NawazIdea — What Every File Does and Why It Exists

This single file replaces all the scattered README files. Every file in this project
is listed here, mapped to the phase it was built in, and explained in plain English.

---

## Project Overview (Plain English)

NawazIdea is an AI-powered support tool. When a customer opens a Salesforce case,
the system automatically reads it, searches a knowledge base (documents you ingested),
generates an answer using GPT, and posts it back to Salesforce. If it is not confident
enough, it flags the case for a human engineer to review instead.

**Phases built so far:**
- Phase 1 → Ingest documents (PDFs, URLs) into a knowledge base
- Phase 2 → Search that knowledge base and generate answers
- Phase 3 → Connect to Salesforce and automatically handle new cases
- Phase 4 → Track every case the system touches (in memory)

---

## Root Level

| File | Phase | What it does |
|------|-------|--------------|
| `.env` | All | Stores secret keys and settings (API keys, database URL, thresholds). Never committed to Git. |
| `requirements.txt` | All | Lists every Python package the backend needs (`pip install -r requirements.txt`). |
| `README.md` | All | High-level project overview. Start here if sharing with someone new. |
| `Explanation.md` | All | **This file.** Maps every file to its phase and purpose. |

---

## backend/ — Python API Server

### Core Files (used by all phases)

| File | Phase | What it does |
|------|-------|--------------|
| `backend/main.py` | All | The entry point. Starts the FastAPI server, sets up the database indexes, registers all the API routes, and launches the Salesforce polling loop in the background. |
| `backend/config.py` | All | Reads your `.env` file and makes every setting available to the rest of the code (API keys, thresholds, poll interval, etc.). |
| `backend/__init__.py` | All | Empty marker file — tells Python that `backend` is a package. |
| `backend/README.md` | All | Backend overview (Codex-generated). Superseded by this file. |

---

### backend/models/ — Data Shapes

| File | Phase | What it does |
|------|-------|--------------|
| `backend/models/schemas.py` | 1 & 2 | Defines what request and response data looks like (e.g., what fields a document has, what a retrieval response contains). Used everywhere. |
| `backend/models/case_store.py` | 4 | In-memory store that tracks every case the system has processed (answered, flagged, escalated). Resets when the server restarts — no database needed. |
| `backend/models/__init__.py` | 1 | Empty marker file. |
| `backend/models/README.md` | 4 | Explains the case store (Codex-generated). |

---

### backend/ingestion/ — Phase 1: Load Documents into Knowledge Base

This folder handles turning raw documents (PDFs, web pages) into searchable data stored in Neo4j.

| File | Phase | What it does |
|------|-------|--------------|
| `backend/ingestion/pdf_extractor.py` | 1 | Reads a PDF file and pulls out the text, page by page. Uses PyMuPDF. |
| `backend/ingestion/url_extractor.py` | 1 | Fetches a web page, strips HTML tags to get readable text, and can also discover links on the page for crawling. |
| `backend/ingestion/chunker.py` | 1 | Splits long text into smaller overlapping pieces (chunks) so each one fits within the AI model's token limit. Max 512 tokens, 64-token overlap. |
| `backend/ingestion/embedder.py` | 1 | Converts each chunk of text into a vector (a list of 1536 numbers) using OpenAI's embedding model. Also contains `retry_async()` — a helper that retries failed API calls automatically. |
| `backend/ingestion/entity_extractor.py` | 1 | Sends each chunk to GPT and asks it to identify key technical terms: products, versions, error messages, symptoms, root causes, resolutions, and features. |
| `backend/ingestion/graph_writer.py` | 1 | Saves everything to Neo4j: creates Document and Chunk nodes, links them together, stores embeddings, creates fulltext and vector search indexes. Also handles deleting and listing documents. |
| `backend/ingestion/__init__.py` | 1 | Empty marker file. |

---

### backend/retrieval/ — Phase 2: Search and Answer

This folder handles taking a question and finding the best answer from the knowledge base.

| File | Phase | What it does |
|------|-------|--------------|
| `backend/retrieval/vector_searcher.py` | 2 | Converts the question into a vector and finds the most similar chunks in Neo4j using cosine similarity (semantic search). |
| `backend/retrieval/fulltext_searcher.py` | 2 | Searches for chunks that contain the exact words from the question (keyword search). Works alongside vector search. |
| `backend/retrieval/graph_expander.py` | 2 | After finding initial chunks, follows relationship edges in Neo4j to pull in related chunks that mention the same entities. |
| `backend/retrieval/result_combiner.py` | 2 | Merges results from vector, fulltext, and graph search. Removes duplicates. Picks the highest score as the confidence level. |
| `backend/retrieval/answer_generator.py` | 2 | Sends the retrieved chunks to GPT and asks it to write a clear answer. If no relevant chunks exist, returns a fallback message. |
| `backend/retrieval/__init__.py` | 2 | Empty marker file. |
| `backend/retrieval/README.md` | 2 | Explains retrieval pipeline (Codex-generated). Superseded by this file. |

---

### backend/routers/ — API Endpoints

These files define what URLs the API exposes and what happens when you call them.

| File | Phase | What it does |
|------|-------|--------------|
| `backend/routers/ingestion.py` | 1 | Handles: `POST /upload-pdf`, `POST /ingest-url`, `GET /documents`, `DELETE /documents/{id}`, `GET /health`. These are the endpoints used by the frontend to add/remove knowledge base documents. |
| `backend/routers/retrieval.py` | 2 | Handles: `POST /api/v1/retriever`. Accepts a question and returns an answer. Supports 4 search modes: `vector`, `fulltext`, `graph_vector`, `graph_vector_fulltext`. |
| `backend/routers/cases.py` | 4 | Handles: `GET /cases`, `GET /cases/summary`, `GET /cases/{id}`, `POST /cases/{id}/resolve`, `POST /cases/{id}/escalate`. Lets you view and manage cases the system has touched. |
| `backend/routers/__init__.py` | 1 | Empty marker file. |
| `backend/routers/README.md` | All | Explains the routers (Codex-generated). |

---

### backend/integrations/ — Phase 3: Salesforce Connection

| File | Phase | What it does |
|------|-------|--------------|
| `backend/integrations/salesforce_client.py` | 3 | Everything related to talking to Salesforce: authenticates using OAuth2 Client Credentials flow, fetches new unprocessed cases, posts AI-generated answers as internal case comments, and flags cases for human review. Uses a custom Salesforce field `CasePilot1_Processed__c` to mark cases already handled. |
| `backend/integrations/__init__.py` | 3 | Empty marker file. |
| `backend/integrations/README.md` | 3 | Explains the Salesforce client (Codex-generated). Superseded by this file. |

---

### backend/agents/ — Phase 3: Automation Loop

| File | Phase | What it does |
|------|-------|--------------|
| `backend/agents/case_listener.py` | 3 | Runs a loop every 10 seconds: fetches new Salesforce cases, calls the retrieval API for each one, checks the confidence score, then either posts an answer or flags for human review. |
| `backend/agents/agent_decision.py` | 3 | Contains the two actions: `handle_high_confidence()` (post the AI answer) and `handle_low_confidence()` (flag for human review). |
| `backend/agents/__init__.py` | 3 | Empty marker file. |
| `backend/agents/README.md` | 3 | Explains the agent loop (Codex-generated). Superseded by this file. |

---

### backend/tests/ — Automated Tests

| File | Phase | What it does |
|------|-------|--------------|
| `backend/tests/test_ingestion.py` | 1 | Tests for document upload, URL ingestion, listing, and deletion. |
| `backend/tests/test_retrieval.py` | 2 | Tests for the retrieval API and answer generation. |
| `backend/tests/test_phase3.py` | 3 | Tests for Salesforce client and the polling loop. |
| `backend/tests/test_phase4.py` | 4 | Tests for the case store and case management endpoints. |

Run all tests with: `pytest backend/tests/`

---

## frontend/ — React Web Interface

The frontend is a browser UI you open to manage the knowledge base. It talks to the backend API.

| File | Phase | What it does |
|------|-------|--------------|
| `frontend/src/api.js` | 1 | All API calls in one place: upload PDF, ingest URL, list documents, delete document. |
| `frontend/src/App.jsx` | 1 | Root component. Manages switching between the Ingest tab and Status tab. |
| `frontend/src/components/IngestTab.jsx` | 1 | Form to add new documents: paste a URL (single page or crawl with pattern filter), or drag-and-drop a PDF. |
| `frontend/src/components/StatusTab.jsx` | 1 | Shows all ingested documents with their status badges. Lets you delete a document (with confirmation). Auto-refreshes while documents are being processed. |
| `frontend/src/components/DropZone.jsx` | 1 | The drag-and-drop area used by IngestTab for PDFs. |
| `frontend/src/components/StatusBadge.jsx` | 1 | Colored badge showing document status (processing, ready, failed). |
| `frontend/src/styles.css` | 1 | All CSS styling for the frontend. |
| `frontend/index.html` | 1 | HTML shell that React mounts into. |
| `frontend/vite.config.js` | 1 | Vite build config. Also sets up a proxy so `/api` calls from the browser go to `localhost:8000` (the backend). |
| `frontend/package.json` | 1 | Lists frontend dependencies (React, Vite). |
| `frontend/package-lock.json` | 1 | Locks exact dependency versions (auto-generated). |
| `frontend/README.md` | 1 | Frontend overview (Codex-generated). Superseded by this file. |

---

## Key Settings in .env

| Variable | What it controls |
|----------|-----------------|
| `OPENAI_API_KEY` | Authenticates with OpenAI for embeddings and GPT answers |
| `NEO4J_URI` | Address of your Neo4j AuraDB instance |
| `NEO4J_USERNAME` / `NEO4J_PASSWORD` | Neo4j login credentials |
| `SALESFORCE_CLIENT_ID` / `SALESFORCE_CLIENT_SECRET` | OAuth2 credentials for Salesforce External Client App |
| `SALESFORCE_INSTANCE_URL` | Your Salesforce org URL (e.g. `https://yourorg.my.salesforce.com`) |
| `CONFIDENCE_THRESHOLD` | Score below which the system flags for human review instead of auto-answering (currently `0.6`) |
| `SALESFORCE_POLL_INTERVAL` | How often (in seconds) to check Salesforce for new cases (currently `10`) |
| `OPENAI_MODEL` | GPT model used for answers (e.g. `gpt-4o` or `gpt-5.4-mini`) |

---

## How It All Connects (One Flow)

```
Customer opens Salesforce case
        ↓
case_listener.py polls Salesforce every 10s
        ↓
salesforce_client.py fetches new cases (CasePilot1_Processed__c = false)
        ↓
routers/retrieval.py receives the question
        ↓
vector_searcher + fulltext_searcher + graph_expander find relevant chunks
        ↓
result_combiner.py merges and scores results
        ↓
answer_generator.py sends chunks + question to GPT → gets answer
        ↓
confidence >= 0.6 ?
   YES → salesforce_client posts AI answer as internal Salesforce comment
    NO → salesforce_client flags case for human review (Priority: High)
        ↓
CasePilot1_Processed__c set to True → case not processed again
```

---

## Phases Still to Build

| Phase | What it will do |
|-------|----------------|
| Phase 5 | Send a Webex message to the engineer when a case is flagged for human review |
| Phase 6 | Learn from cases that engineers resolve — add those resolutions back into the knowledge base |
| Phase 7 | Analytics dashboard showing resolution rates, confidence trends, time saved |
