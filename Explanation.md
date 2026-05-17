# NawazIdea — What Every File Does and Why It Exists

This single file replaces all the scattered README files. Every file in this project
is listed here, mapped to the phase it was built in, and explained in plain English.

---

## Project Overview (Plain English)

NawazIdea is an AI-powered support tool. When a customer opens a Salesforce case,
the system automatically reads it, searches a knowledge base (documents you ingested),
generates an answer using GPT, and posts it back to Salesforce. If it is not confident
enough, it flags the case for a human engineer to review instead. When the customer
confirms the issue is resolved, the case is auto-closed and the Q&A is added back
into the knowledge base so the AI gets smarter over time.

**Phases built:**
- Phase 1 → Ingest documents (PDFs, URLs) into a knowledge base
- Phase 2 → Search that knowledge base and generate answers
- Phase 3 → Connect to Salesforce and automatically handle new cases
- Phase 4 → Track every case the system touches (in memory)
- Phase 5 → Notify engineer on Webex when a case needs human review
- Phase 6 → Monitor replies, auto-close satisfied cases, self-learn from resolutions

---

## Root Level

| File | Phase | What it does |
|------|-------|--------------|
| `.env` | All | Stores secret keys and settings. Never committed to Git. |
| `requirements.txt` | All | Lists every Python package the backend needs. |
| `README.md` | All | High-level project overview. |
| `Explanation.md` | All | **This file.** Maps every file to its phase and purpose. |

---

## backend/ — Python API Server

### Core Files (used by all phases)

| File | Phase | What it does |
|------|-------|--------------|
| `backend/main.py` | All | Entry point. Starts FastAPI, creates Neo4j indexes, registers all routers, and launches two background loops: one for new cases (every 10s) and one for customer replies (every 60s). |
| `backend/config.py` | All | Reads `.env` and exposes all settings to the rest of the code. Includes Salesforce, OpenAI, Neo4j, Webex, polling interval, confidence threshold, and self-learning toggle. |
| `backend/__init__.py` | All | Empty marker file. |
| `backend/README.md` | All | Backend overview (Codex-generated). |

---

### backend/models/ — Data Shapes

| File | Phase | What it does |
|------|-------|--------------|
| `backend/models/schemas.py` | 1 & 2 | Defines what request and response data looks like. Used by all API endpoints. |
| `backend/models/case_store.py` | 4 | In-memory store tracking every case the system processed. Tracks status: processed, resolved, escalated. Resets on server restart. |
| `backend/models/__init__.py` | 1 | Empty marker file. |
| `backend/models/README.md` | 4 | Explains the case store. |

---

### backend/ingestion/ — Phase 1: Load Documents into Knowledge Base

| File | Phase | What it does |
|------|-------|--------------|
| `backend/ingestion/pdf_extractor.py` | 1 | Reads a PDF and extracts text page by page using PyMuPDF. |
| `backend/ingestion/url_extractor.py` | 1 | Fetches a web page, strips HTML, and can crawl links matching a pattern. |
| `backend/ingestion/chunker.py` | 1 | Splits long text into overlapping chunks (max 512 tokens, 64-token overlap). |
| `backend/ingestion/embedder.py` | 1 | Converts each chunk into a 1536-dimension vector using OpenAI embeddings. Also contains `retry_async()` for automatic retries on API failures. |
| `backend/ingestion/entity_extractor.py` | 1 | Uses GPT to extract key technical terms from each chunk: products, versions, errors, symptoms, root causes, resolutions, features. |
| `backend/ingestion/graph_writer.py` | 1 | Saves everything to Neo4j: Document and Chunk nodes, embeddings, relationships. Creates vector and fulltext indexes. Handles delete and list. |
| `backend/ingestion/__init__.py` | 1 | Empty marker file. |

---

### backend/retrieval/ — Phase 2: Search and Answer

| File | Phase | What it does |
|------|-------|--------------|
| `backend/retrieval/vector_searcher.py` | 2 | Embeds the question and finds the most semantically similar chunks in Neo4j. |
| `backend/retrieval/fulltext_searcher.py` | 2 | Finds chunks containing the exact words from the question (keyword search). |
| `backend/retrieval/graph_expander.py` | 2 | Follows relationship edges in Neo4j to pull in additional related chunks. |
| `backend/retrieval/result_combiner.py` | 2 | Merges all results, removes duplicates, picks highest score as confidence. |
| `backend/retrieval/answer_generator.py` | 2 & 6 | Sends chunks + question to GPT to generate an answer. Key rules: only answer if the context directly covers the question topic — do not use general knowledge to fill gaps. If GPT returns the fallback message, confidence is forced to 0.0 so the case is always escalated. |
| `backend/retrieval/__init__.py` | 2 | Empty marker file. |
| `backend/retrieval/README.md` | 2 | Explains retrieval pipeline. |

---

### backend/routers/ — API Endpoints

| File | Phase | What it does |
|------|-------|--------------|
| `backend/routers/ingestion.py` | 1 | `POST /upload-pdf`, `POST /ingest-url`, `GET /documents`, `DELETE /documents/{id}`, `GET /health`. |
| `backend/routers/retrieval.py` | 2 | `POST /api/v1/retriever`. Accepts question, returns answer. Supports 4 modes: vector, fulltext, graph_vector, graph_vector_fulltext. |
| `backend/routers/cases.py` | 4 | `GET /cases`, `GET /cases/summary`, `GET /cases/{id}`, `POST /cases/{id}/resolve`, `POST /cases/{id}/escalate`. |
| `backend/routers/__init__.py` | 1 | Empty marker file. |
| `backend/routers/README.md` | All | Explains the routers. |

---

### backend/integrations/ — External Services

| File | Phase | What it does |
|------|-------|--------------|
| `backend/integrations/salesforce_client.py` | 3 & 6 | All Salesforce communication. Phase 3: OAuth2 login, fetch new cases, post answers, flag for review. Phase 6: fetch in-progress cases, read customer replies, close cases, create Knowledge Articles, update reply-checked timestamp. |
| `backend/integrations/webex_client.py` | 5 | Sends Webex notifications to the engineer. Disabled silently if `WEBEX_BOT_TOKEN` or `WEBEX_ROOM_ID` is missing. |
| `backend/integrations/__init__.py` | 3 | Empty marker file. |
| `backend/integrations/README.md` | 3 & 5 & 6 | Explains Salesforce client, Webex client, and Phase 6 new methods. |

---

### backend/agents/ — Automation Loops & Decision Logic

| File | Phase | What it does |
|------|-------|--------------|
| `backend/agents/case_listener.py` | 3 & 6 | Two background loops. Loop 1 (every 10s): fetches new Salesforce cases and processes them. Loop 2 (every 60s): checks in-progress cases for new customer replies and triggers reply handling. |
| `backend/agents/agent_decision.py` | 3 & 5 | `handle_high_confidence()` posts AI answer. `handle_low_confidence()` flags case and sends Webex notification to engineer. |
| `backend/agents/reply_classifier.py` | 6 | Uses GPT to classify a customer reply into one of three intents: SATISFIED (customer confirms resolution), STUCK (solution didn't work), UNCLEAR (requesting a call or human help). Call/meeting requests are always UNCLEAR, never STUCK. |
| `backend/agents/reply_handler.py` | 6 | Orchestrates the reply flow. SATISFIED → close case + create KB article + Webex message with article link. STUCK → flag case + Webex alert to engineer. UNCLEAR → Webex alert asking engineer to respond. Always updates the last-reply-checked timestamp. |
| `backend/agents/self_learner.py` | 6 | Two functions: `generate_kb_article_body()` uses GPT to read the full case history and write a proper KB article. `ingest_resolved_qa()` strips PII from the Q&A then chunks, embeds, extracts entities, and writes it into Neo4j so future similar questions get answered automatically. |
| `backend/agents/__init__.py` | 3 | Empty marker file. |
| `backend/agents/README.md` | 3 & 6 | Explains both polling loops, decision logic, reply classification, and self-learning. |

---

### backend/tests/ — Automated Tests

| File | Phase | What it does |
|------|-------|--------------|
| `backend/tests/test_ingestion.py` | 1 | Tests for PDF upload, URL ingestion, document listing and deletion. |
| `backend/tests/test_retrieval.py` | 2 | Tests for retrieval API and answer generation. |
| `backend/tests/test_phase3.py` | 3 | Tests for Salesforce client and new-case polling loop. |
| `backend/tests/test_phase4.py` | 4 | Tests for case store and case management endpoints. |
| `backend/tests/test_phase5.py` | 5 | Tests for WebexClient — disabled when token missing, correct payload, error handling. |
| `backend/tests/test_phase6.py` | 6 | Tests for reply classifier, reply handler, self-learner, and new Salesforce methods. |

Run all tests: `pytest backend/tests/`

---

## frontend/ — React Web Interface

| File | Phase | What it does |
|------|-------|--------------|
| `frontend/src/api.js` | 1 | All API calls: upload PDF, ingest URL, list documents, delete document. |
| `frontend/src/App.jsx` | 1 | Root component. Manages tab switching between Ingest and Status. |
| `frontend/src/components/IngestTab.jsx` | 1 | Form to add documents via URL or PDF drag-and-drop. |
| `frontend/src/components/StatusTab.jsx` | 1 | Shows ingested documents, status badges, delete with confirmation, auto-refresh. |
| `frontend/src/components/DropZone.jsx` | 1 | Drag-and-drop area for PDFs. |
| `frontend/src/components/StatusBadge.jsx` | 1 | Colored badge showing processing / ready / failed. |
| `frontend/src/styles.css` | 1 | All CSS styling. |
| `frontend/index.html` | 1 | HTML shell that React mounts into. |
| `frontend/vite.config.js` | 1 | Vite build config. Proxies `/api` calls to `localhost:8000`. |
| `frontend/package.json` | 1 | Frontend dependencies (React, Vite). |
| `frontend/package-lock.json` | 1 | Auto-generated dependency lock file. |
| `frontend/README.md` | 1 | Frontend overview. |

---

## Key Settings in .env

| Variable | What it controls |
|----------|-----------------|
| `OPENAI_API_KEY` | OpenAI authentication for embeddings and GPT |
| `OPENAI_LLM_MODEL` | GPT model for answers (e.g. `gpt-5.4-mini`) |
| `OPENAI_EMBEDDING_MODEL` | Embedding model (default: `text-embedding-3-small`) |
| `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD` | Neo4j AuraDB connection |
| `SALESFORCE_CLIENT_ID` / `SALESFORCE_CLIENT_SECRET` | Salesforce OAuth2 credentials |
| `SALESFORCE_INSTANCE_URL` | Your Salesforce org URL |
| `CONFIDENCE_THRESHOLD` | Below this score the case is flagged (default: `0.6`) |
| `SALESFORCE_POLL_INTERVAL` | Seconds between new-case checks (default: `10`) |
| `REPLY_POLL_INTERVAL` | Seconds between reply checks on in-progress cases (default: `60`) |
| `SELF_LEARNING_ENABLED` | Whether resolved Q&A is ingested back into Neo4j (default: `true`) |
| `WEBEX_BOT_TOKEN` | Webex bot token for sending notifications |
| `WEBEX_ROOM_ID` | Webex room where notifications are sent |

---

## Salesforce Custom Fields Required

| Field | Object | Type | Purpose |
|-------|--------|------|---------|
| `CasePilot1_Processed__c` | Case | Checkbox | Marks cases already handled — prevents duplicate processing |
| `CasePilot1_LastReplyChecked_c__c` | Case | DateTime | Tracks when replies were last checked — prevents re-reading old comments |
| `Body__c` | Knowledge | Rich Text Area | Stores the body of auto-generated knowledge articles |

---

## How It All Connects (Full Flow)

```
── NEW CASE FLOW (every 10 seconds) ──────────────────────────────

Customer opens Salesforce case
        ↓
case_listener.py fetches cases where CasePilot1_Processed__c = false
        ↓
vector + fulltext + graph search finds relevant KB chunks
        ↓
GPT reads chunks — answers only if context directly covers the question
        ↓
confidence >= 0.6 AND GPT gave a real answer?
   YES → Post AI answer as internal Salesforce comment (auto-answered)
    NO → Post "human review required" + Webex alert to engineer

── REPLY MONITORING FLOW (every 60 seconds) ──────────────────────

case_listener.py checks In Progress cases for new customer comments
(skips comments starting with [NawazIdea — those are our own posts)
        ↓
Customer replied?
   NO  → Skip, update last-checked timestamp
   YES → reply_classifier.py asks GPT: SATISFIED / STUCK / UNCLEAR?
              ↓
        SATISFIED → close_case() in Salesforce
                  → generate_kb_article_body() — GPT reads full case
                    history and writes a proper KB article
                  → ingest_resolved_qa() — strip PII, chunk, embed,
                    write into Neo4j (AI gets smarter)
                  → create_knowledge_article() — draft article in
                    Salesforce Knowledge for engineer to review
                  → Webex: "Case closed + link to draft article"
              ↓
        STUCK   → flag_for_human_review() in Salesforce
                → Webex: "Customer still stuck, please review"
              ↓
        UNCLEAR → Webex: "Customer may want a call, please respond"
```

---

## Phases Still to Build

| Phase | What it will do |
|-------|----------------|
| Phase 7 | Analytics dashboard — resolution rates, confidence trends, time saved, KB growth |
