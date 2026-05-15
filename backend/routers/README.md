# Routers Folder

## What This Folder Does

This folder contains all API endpoints. An API endpoint is a web address that lets the frontend, an agent, or another tool ask the backend to do something. Each router file groups related endpoints together.

## What Each Router File Handles

- `ingestion.py` handles PDF upload, URL ingestion, document listing, document deletion, and health checks.
- `retrieval.py` handles question answering from the knowledge base.
- `cases.py` handles case tracking, case summary, resolving cases, and escalating cases.

## What Each cases.py Endpoint Does

- `GET /cases` shows every case the agent has processed.
- `GET /cases/summary` shows counts for processed, automatic, flagged, resolved, and escalated cases.
- `GET /cases/{case_id}` shows one case by its ID.
- `POST /cases/{case_id}/resolve` marks one case as resolved.
- `POST /cases/{case_id}/escalate` marks one case as escalated.

## What Resolve And Escalate Do In Salesforce

The resolve endpoint updates Salesforce by closing the case. The escalate endpoint updates Salesforce by setting the case priority to High and adding an internal comment. If Salesforce is not available, the local case store is still updated.

## SUMMARY

Routers connect outside requests to backend logic.
The frontend calls router endpoints.
The Salesforce agent can use router behavior too.
Ingestion routes add knowledge.
Retrieval routes answer questions.
Case routes show and manage agent decisions.

## HOW TO TEST

All endpoints are visible at this page once the backend is running:

```text
http://127.0.0.1:8000/docs
```

Get all tracked cases:

```bash
curl http://127.0.0.1:8000/cases
```

Get case summary counts:

```bash
curl http://127.0.0.1:8000/cases/summary
```

Mark a case as resolved:

```bash
curl -X POST http://127.0.0.1:8000/cases/CASE_ID/resolve
```
