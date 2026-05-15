# Retrieval Folder

## 1. What This Retrieval Folder Does

This folder takes a question, searches the knowledge base stored in Neo4j (the database that stores documents, chunks, and connections), and returns the best answer with the sources used. It is the second half of the system. Phase 1 stored the knowledge. Phase 2, which is this folder, finds that knowledge when a user asks a question.

## 2. What Each File Does

- `vector_searcher.py` searches by meaning using embeddings (lists of numbers that represent the meaning of text).
- `graph_expander.py` finds extra chunks by following graph connections (links between saved items) from the first search results.
- `fulltext_searcher.py` searches by matching words in the question against saved chunk text.
- `result_combiner.py` joins search results together, removes duplicates, and keeps the best scoring chunks.
- `answer_generator.py` sends the best chunks and the question to OpenAI so it can write a final answer.
- `routers/retrieval.py` creates the API endpoint (the web address the frontend or another tool can call) for asking questions.

## 3. How The Four Search Modes Work

- `vector` does meaning-based search. It can find useful chunks even when the exact words are different.
- `graph` starts with meaning-based search, then follows connections between related chunks and entities. This helps find nearby information that may explain the answer.
- `fulltext` does keyword matching. It is useful when the question includes exact terms, product names, or error codes.
- `graph_vector_fulltext` runs meaning-based search and keyword search, then follows graph connections. This is the recommended mode because it uses all three search methods together.

## 4. What The API Endpoint Does

`POST /api/v1/retriever` receives a question and searches the knowledge base for an answer. It returns a message, source links, chunk details, response time, mode, and confidence score.

| Parameter | What it is | Why someone would use it |
|---|---|---|
| `question` | The question the user wants answered. | This is the main text the system searches for. |
| `session_id` | A text ID for the current chat or request. | The API sends it back so the caller can match the response to the request. |
| `mode` | The search method to use. | Use it to choose `vector`, `graph`, `fulltext`, or `graph_vector_fulltext`. |
| `response_type` | The kind of response to return. | Use `answer` for a written answer, or `retrieval_only` to see only the chunks found. |
| `document_names` | A comma-separated list of document titles. | Use it to search only inside specific documents. |
| `top_k` | The number of top results to keep. | Use it to control how many chunks are considered. |
| `model` | The OpenAI model used to write the answer. | Use it when you want a different answer-writing model. |
| `database` | The database name sent in the form body. | It is accepted and logged, but it is not used for filtering in this phase. |

## 5. What The Confidence Score Means

The confidence score is a number between 0 and 1. It shows how closely the best retrieved content matches the question. A higher number means the system found content that is closer to the question. The `0.8` threshold means the system treats scores at or above `0.8` as strong matches, but the API still returns the answer either way.

## 6. How The Retrieval Pipeline Works Step By Step

1. A question arrives at `POST /api/v1/retriever`.
2. The router gets the Neo4j driver (the database connection) from the running backend app.
3. The router checks the selected search mode.
4. The vector searcher may turn the question into an embedding and search by meaning.
5. The fulltext searcher may search for matching words in chunk text.
6. The graph expander may find extra chunks connected to the first results.
7. The result combiner removes duplicate chunks and sorts the best chunks first.
8. If an answer is requested, the answer generator sends the question and chunks to OpenAI.
9. The API returns the answer, source links, chunk details, response time, mode, and confidence score.

## SUMMARY

A question arrives at the retrieval API.
The system searches Neo4j for chunks that match the question.
It can search by meaning, keywords, graph connections, or all three.
The best chunks are combined and ranked.
OpenAI writes an answer using only those chunks.
The response includes source links and a confidence score.
The caller can decide how much to trust the answer.

## HOW TO RUN

The retrieval API starts automatically when the backend starts. There is no separate command for this folder.

Once the backend is running, test the endpoint with this command:

```bash
curl -X POST "http://localhost:8000/api/v1/retriever?question=How%20do%20I%20reset%20a%20router%3F&session_id=test-session-1&mode=graph_vector_fulltext" \
  -F "database=nawazidea_kb"
```

The backend must be running first. Read the backend guide here:

```text
../README.md
```
