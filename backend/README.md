# CasePilot Backend

## 1. What This Backend Does

This backend receives documents, such as PDFs and web pages. It reads the text, breaks the text into small pieces, converts each piece into an embedding (a list of numbers that represents the meaning of text), extracts named things like products and error codes, and stores everything in Neo4j (a database that stores items and the relationships between them). This lets CasePilot search the knowledge base intelligently later.

## 2. What Each Folder And File Does

### ingestion/

- `ingestion/__init__.py` tells Python that the `ingestion` folder is a package (a folder of Python code that can be imported).
- `ingestion/pdf_extractor.py` opens a PDF file and pulls text from each page.
- `ingestion/url_extractor.py` downloads a web page, removes page code like scripts and styles, and returns plain readable text.
- `ingestion/chunker.py` splits long document text into smaller chunks so each piece can be processed.
- `ingestion/embedder.py` sends chunk text to OpenAI and gets back an embedding (numbers that represent meaning).
- `ingestion/entity_extractor.py` sends chunk text to OpenAI and asks it to find named things like products, versions, symptoms, and errors.
- `ingestion/graph_writer.py` writes documents, chunks, entities, and relationships into Neo4j.

### routers/

- `routers/__init__.py` tells Python that the `routers` folder is a package.
- `routers/ingestion.py` defines the web addresses that users or the frontend can call to upload PDFs, ingest URLs, list documents, and check health.

### models/

- `models/__init__.py` tells Python that the `models` folder is a package.
- `models/schemas.py` defines the shapes of the data that the API (the way the frontend asks the backend to do work) receives and sends back.

### tests/

- `tests/test_ingestion.py` checks that the PDF reader, chunker, entity extraction, duplicate URL check, and URL pattern filter work as expected.

### Root Files

- `__init__.py` tells Python that the `backend` folder is a package.
- `main.py` creates the FastAPI app (the Python web server), connects the routes (web addresses), and creates the Neo4j vector index (a database helper for searching embeddings) when the server starts.
- `config.py` reads settings from the `.env` file so secrets and service addresses are not hard-coded.

## 3. What The API Endpoints Do

### POST /upload-pdf

- What you send: A PDF file in a form field named `file`.
- What it does: It checks that the file is a PDF, checks if a PDF with the same title already exists, then starts processing it in the background.
- What it gives back: A document ID and a status such as `processing` or `duplicate`.

### POST /ingest-url

- What you send: A JSON body (structured text data) with a URL, a crawl mode, and optionally a URL pattern.
- What it does: It checks if the URL was already ingested. For single mode it processes one page, and for crawl mode it finds linked pages and filters them by the pattern if one was provided.
- What it gives back: A list of document IDs and a status such as `processing` or `duplicate`.

### GET /documents

- What you send: Nothing.
- What it does: It asks Neo4j for the documents that have been added.
- What it gives back: A list of documents with source, type, status, upload time, and chunk count.

### GET /health

- What you send: Nothing.
- What it does: It checks that the backend server is awake.
- What it gives back: `{ "status": "ok" }`.

## 4. What The Ingestion Pipeline Does Step By Step

1. A user uploads a PDF through the API.
2. The backend checks the file type and checks whether a document with the same title already exists.
3. The backend saves the PDF temporarily so it can read it.
4. The PDF extractor opens the file and pulls text from each page.
5. The chunker splits the page text into smaller chunks with a little overlap between chunks.
6. For each chunk, the backend sends the text to OpenAI for an embedding and also asks OpenAI to extract named entities.
7. The graph writer stores the document, chunks, embeddings, entities, and relationships in Neo4j.
8. After all chunks are stored, the backend links chunks that mention at least two of the same entities.
9. The document status is changed to `completed` if everything worked, or `failed` if something went wrong.

## 5. What The External Services Are And Why They Are Needed

### OpenAI

OpenAI is used for two jobs in this project. First, it creates embeddings, which are lists of numbers that represent the meaning of each chunk. Second, it reads each chunk and extracts named things like product names, versions, symptoms, root causes, fixes, error codes, and features.

### Neo4j

Neo4j is the database used by CasePilot. It stores documents, chunks, and named entities as nodes (saved items), and it stores relationships between them. It also stores embeddings so the app can support meaning-based search later.

## 6. Environment Variables

| Variable | What it is | Why it is needed |
|---|---|---|
| `OPENAI_API_KEY` | Your secret key for OpenAI. | The backend needs it to call OpenAI for embeddings and entity extraction. |
| `OPENAI_EMBEDDING_MODEL` | The OpenAI model used to create embeddings. | The backend uses `text-embedding-3-small` to turn chunks into meaning numbers. |
| `OPENAI_LLM_MODEL` | The OpenAI model used to read text and extract entities. | The backend uses `gpt-4o` to find products, errors, symptoms, and other named things. |
| `NEO4J_URI` | The address of your Neo4j database. | The backend needs it to connect to the database. |
| `NEO4J_USERNAME` | The username for Neo4j. | The backend needs it to sign in to Neo4j. |
| `NEO4J_PASSWORD` | The password for Neo4j. | The backend needs it to sign in to Neo4j. |
| `CONFIDENCE_THRESHOLD` | A number for future confidence checks. | It is available as a setting for deciding how sure the system should be. |
| `ENVIRONMENT` | The name of the current environment, such as `development`. | It helps show whether the app is running locally or somewhere else. |

## SUMMARY

The user uploads a PDF to the backend.
The backend checks that the file is valid and not already stored.
The backend reads text from the PDF page by page.
The text is split into smaller chunks.
OpenAI creates embeddings and extracts named entities from each chunk.
Neo4j stores the document, chunks, entities, and relationships.
The document becomes ready for intelligent search later.

## HOW TO RUN

1. Create and activate a Python virtual environment.

   ```bash
   cd /Users/nawaz/Desktop/Vibe/WebApp
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies from `requirements.txt`.

   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file and fill in the required values.

   ```bash
   touch .env
   ```

   Add these values to `.env`:

   ```env
   OPENAI_API_KEY=
   OPENAI_EMBEDDING_MODEL=text-embedding-3-small
   OPENAI_LLM_MODEL=gpt-4o
   NEO4J_URI=
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=
   CONFIDENCE_THRESHOLD=0.8
   ENVIRONMENT=development
   ```

4. Start the server with `uvicorn` (the tool that runs the FastAPI web server).

   ```bash
   uvicorn backend.main:app --reload
   ```

   Open this page to check the server:

   ```text
   http://127.0.0.1:8000/health
   ```
