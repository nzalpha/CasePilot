# CasePilot

## Project Overview

CasePilot is an AI-powered customer support case resolution system.  CasePilot reads your knowledge base (your support documents and web pages), finds answers for Salesforce (a customer support case system) cases, and helps the support team answer faster. Over time, resolved cases can become new knowledge for future answers.

## How The System Works — Big Picture

1. Documents are uploaded and stored in a database (a place where information is saved).
2. A customer creates a case in Salesforce.
3. The agent finds the best answer from the database.
4. If confident enough, it posts the answer automatically.
5. If not confident, it flags the case for a human to review.
6. Every resolved case feeds back as new knowledge.

## Phase 1 — Ingestion ✅ Complete

Phase 1 reads PDFs and web pages. It breaks them into small chunks, creates embeddings (numbers that represent text meaning), extracts named things like products and errors, and stores everything in Neo4j (a graph database that stores items and their connections).

What was built:

- `backend/ingestion/` for PDF reading, URL reading, chunking, embeddings, entity extraction, and Neo4j writing.
- `backend/routers/ingestion.py` for upload and document management endpoints.
- `backend/models/schemas.py` for shared data shapes.

APIs (ways for software to ask the backend to do work) and endpoints (specific web addresses):

- `POST /upload-pdf`
- `POST /ingest-url`
- `GET /documents`
- `DELETE /documents/{id}`
- `GET /health`

How to test:

- Start the backend.
- Open `http://127.0.0.1:8000/docs`.
- Upload a PDF or submit a URL.

## Phase 2 — Retrieval ✅ Complete

Phase 2 takes a question and searches the stored knowledge. It searches three ways at once: meaning-based search, keyword search, and connection-based search. It combines the best chunks and uses GPT-4o (an OpenAI model that writes text) to write a clear answer with a confidence score between 0 and 1.

What was built:

- `backend/retrieval/` for vector search, graph expansion, full-text search, result combining, and answer generation.
- `backend/routers/retrieval.py` for the question-answering endpoint.

APIs and endpoints:

- `POST /api/v1/retriever`

How to test:

- Open `http://127.0.0.1:8000/docs`.
- Use `POST /api/v1/retriever`.
- Enter a question with `mode=graph_vector_fulltext`.

## Phase 3 — Salesforce Agent ✅ Complete

Phase 3 polls Salesforce every 10 seconds for new cases. For each case, it calls the retrieval API, checks the confidence score, and either posts an answer or flags the case for human review. It runs as a background task inside the backend.

What was built:

- `backend/integrations/salesforce_client.py` for Salesforce login, case reads, comments, and updates.
- `backend/agents/case_listener.py` for polling Salesforce and calling retrieval.
- `backend/agents/agent_decision.py` for deciding whether to answer or flag for review.

APIs and endpoints:

- No public endpoint was added in this phase.
- The agent runs when the backend starts.

How to test:

- Create a new Case in Salesforce with `Status=New`.
- Make sure `NawazIdea_Processed__c` is unchecked.
- Watch the backend terminal for log lines showing the agent decision.

## Phase 4 — Salesforce Case Updates 🔜 Coming Next

Phase 4 will build the full Salesforce update path. It will post answers back to cases, send emails to customers, update case status, and close cases when resolved.

What will be built:

- `backend/integrations/salesforce_updater.py`
- `backend/routers/cases.py`

## Phase 5 — Case Lifecycle Management 🔜 Planned

Phase 5 will classify customer replies as resolved, still open, escalate, or no response. It will send follow-up messages on Day 2 and Day 4, close cases with no response on Day 5, and send Webex messages to engineers when a customer wants to escalate.

What will be built:

- `backend/agents/reply_classifier.py`
- `backend/workers/followup_scheduler.py`
- `backend/integrations/webex_client.py`

## Phase 6 — Self-Learning Loop 🔜 Planned

Phase 6 will create a new knowledge base article from every resolved case. It will remove private customer information first, ask an engineer to approve it, and ingest it back into Neo4j so future cases can use it.

What will be built:

- `backend/kb/pii_remover.py`
- `backend/kb/kb_writer.py`
- `backend/kb/kb_approver.py`
- `frontend/src/pages/KBReviewPage.jsx`

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| API Backend | FastAPI (a Python tool for APIs) + Python | Handles all requests |
| Graph + Vector Database | Neo4j AuraDB | Stores knowledge and embeddings |
| LLM (large language model) | OpenAI GPT-4o | Generates answers and extracts entities |
| Embeddings | OpenAI text-embedding-3-small | Converts text to numbers |
| CRM (customer relationship management) | Salesforce | Where customer cases live |
| Frontend | React + Vite | Builds the upload and status screens |

## Folder Structure

```text
WebApp/                                  # Main project folder.
├── .env                                 # Local secret settings. Do not commit this file.
├── .gitignore                           # Tells Git which local files to ignore.
├── README.md                            # Master project guide.
├── requirements.txt                     # Python package list for the backend.
├── backend/                             # Python backend code.
│   ├── README.md                        # Beginner guide for the backend.
│   ├── __init__.py                      # Marks backend as a Python package.
│   ├── config.py                        # Reads settings from .env.
│   ├── main.py                          # Starts FastAPI and background tasks.
│   ├── agents/                          # Background agent code.
│   │   ├── README.md                    # Beginner guide for agents.
│   │   ├── __init__.py                  # Marks agents as a Python package.
│   │   ├── agent_decision.py            # Chooses automatic answer or human review.
│   │   └── case_listener.py             # Polls Salesforce and calls retrieval.
│   ├── ingestion/                       # Phase 1 document ingestion code.
│   │   ├── __init__.py                  # Marks ingestion as a Python package.
│   │   ├── chunker.py                   # Splits text into smaller chunks.
│   │   ├── embedder.py                  # Creates embeddings with OpenAI.
│   │   ├── entity_extractor.py          # Extracts products, errors, and other names.
│   │   ├── graph_writer.py              # Writes documents and chunks to Neo4j.
│   │   ├── pdf_extractor.py             # Reads text from PDF files.
│   │   └── url_extractor.py             # Reads plain text from web pages.
│   ├── integrations/                    # Code that talks to outside systems.
│   │   ├── README.md                    # Beginner guide for integrations.
│   │   ├── __init__.py                  # Marks integrations as a Python package.
│   │   └── salesforce_client.py         # Talks to Salesforce cases and comments.
│   ├── models/                          # Shared data shapes.
│   │   ├── __init__.py                  # Marks models as a Python package.
│   │   └── schemas.py                   # Defines API request and response shapes.
│   ├── retrieval/                       # Phase 2 answer retrieval code.
│   │   ├── README.md                    # Beginner guide for retrieval.
│   │   ├── __init__.py                  # Marks retrieval as a Python package.
│   │   ├── answer_generator.py          # Writes final answers using OpenAI.
│   │   ├── fulltext_searcher.py         # Finds chunks by keyword match.
│   │   ├── graph_expander.py            # Finds chunks connected to other chunks.
│   │   ├── result_combiner.py           # Combines and ranks search results.
│   │   └── vector_searcher.py           # Finds chunks by meaning.
│   ├── routers/                         # API route files.
│   │   ├── __init__.py                  # Marks routers as a Python package.
│   │   ├── ingestion.py                 # Upload, URL ingest, list, delete, and health routes.
│   │   └── retrieval.py                 # Question-answering route.
│   └── tests/                           # Backend tests.
│       ├── test_ingestion.py            # Tests Phase 1 ingestion behavior.
│       ├── test_phase3.py               # Tests Salesforce agent behavior.
│       └── test_retrieval.py            # Tests Phase 2 retrieval behavior.
└── frontend/                            # React frontend code.
    ├── README.md                        # Beginner guide for the frontend.
    ├── index.html                       # Browser entry page.
    ├── package-lock.json                # Exact installed frontend package versions.
    ├── package.json                     # Frontend scripts and package list.
    ├── vite.config.js                   # Vite settings and backend proxy.
    └── src/                             # Frontend source code.
        ├── App.jsx                      # Main React app and tab switching.
        ├── api.js                       # Browser calls to the backend API.
        ├── styles.css                   # App styling.
        └── components/                  # Frontend UI pieces.
            ├── DropZone.jsx             # PDF drag-and-drop upload box.
            ├── IngestTab.jsx            # URL and PDF ingestion form.
            ├── StatusBadge.jsx          # Colored status label.
            └── StatusTab.jsx            # Document status table and delete action.
```

## Environment Variables

| Variable | What it is | Used in |
|---|---|---|
| `OPENAI_API_KEY` | Secret key for OpenAI. | Phases 1 and 2 |
| `OPENAI_EMBEDDING_MODEL` | Model that creates embeddings. | Phases 1 and 2 |
| `OPENAI_LLM_MODEL` | Model that extracts entities and writes answers. | Phases 1 and 2 |
| `NEO4J_URI` | Address of the Neo4j database. | Phases 1 and 2 |
| `NEO4J_USERNAME` | Neo4j username. | Phases 1 and 2 |
| `NEO4J_PASSWORD` | Neo4j password. | Phases 1 and 2 |
| `CONFIDENCE_THRESHOLD` | Minimum score for automatic answers. | Phase 3 |
| `ENVIRONMENT` | Name of the local or deployed environment. | All phases |
| `SALESFORCE_CLIENT_ID` | Salesforce external client app ID. | Phase 3 |
| `SALESFORCE_CLIENT_SECRET` | Salesforce external client app secret. | Phase 3 |
| `SALESFORCE_INSTANCE_URL` | Salesforce org URL. | Phase 3 |
| `SALESFORCE_USERNAME` | Salesforce username, kept for settings compatibility. | Phase 3 |
| `SALESFORCE_PASSWORD` | Salesforce password, kept for settings compatibility. | Phase 3 |
| `SALESFORCE_SECURITY_TOKEN` | Salesforce security token, kept for settings compatibility. | Phase 3 |
| `SALESFORCE_POLL_INTERVAL` | Seconds between Salesforce checks. | Phase 3 |

## How To Run The Project

1. Clone the repo with Git (a tool for copying code and tracking changes).

   ```bash
   git clone https://github.com/nzalpha/CasePilot.git
   cd CasePilot
   ```

2. Create the `.env` file and fill in all variables.

   ```bash
   touch .env
   ```

   Add the variables from the Environment Variables section.

3. Install dependencies with `uv sync`. uv is a Python package tool.

   ```bash
   uv sync
   ```

4. Start the backend with `uvicorn` (the command that runs FastAPI).

   ```bash
   uvicorn backend.main:app --reload
   ```

5. Open the API docs.

   ```text
   http://127.0.0.1:8000/docs
   ```

6. Start the frontend with `npm` (a JavaScript package tool).

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   Open the URL shown in the terminal.

<!-- MAINTAINER NOTE:
When a new phase is completed, update this file:
1. Change the phase header from 🔜 Planned to ✅ Complete
2. Fill in the "Files built" and "Endpoints" sections
3. Add a "How to test" note for that phase
4. Update the Folder Structure section with new files
5. Add any new environment variables to the table
-->
