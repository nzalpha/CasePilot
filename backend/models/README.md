# Models Folder

## What This Folder Does

This folder stores data shapes and the in-memory case tracking store. A data shape means a clear list of fields that a piece of data should have. The backend uses these shapes so API responses and stored case records stay consistent.

## What case_store.py Does

`case_store.py` is like a notepad that records everything the agent does to each case. It stores the case ID, question, action, confidence score, sources, and current status. It keeps this information in memory while the backend is running.

## What Each CaseRecord Field Means

- `case_id` is the Salesforce ID for the case.
- `case_number` is the human-friendly Salesforce case number.
- `subject` is the short case title.
- `question` is the full question sent to retrieval.
- `action` says whether the agent answered automatically or flagged the case for a human.
- `confidence` is the score from retrieval.
- `answer` is the answer the agent suggested, or empty when a human review is needed.
- `sources` are the links or documents used to make the answer.
- `processed_at` is the time the agent handled the case.
- `status` is the local tracking status, such as processed, resolved, or escalated.

## What The CaseStore Methods Do

- `add` saves a case record and replaces the old record if the same case ID already exists.
- `get` finds one case record by case ID.
- `all` returns all case records with the newest first.
- `update_status` changes the local status for one case.
- `summary` counts total, automatic, human-flagged, resolved, and escalated cases.

## Important Note

The store is in-memory. This means the records live only while the backend server is running. If the server restarts, all records are lost. MongoDB will replace this in a future phase.

## SUMMARY

The agent processes a Salesforce case.
It saves a record in the case store.
The API can show what the agent did.
Engineers can check case status later.
Resolve and escalate actions update the same store.
This gives the project a simple tracking system for now.

## HOW TO RUN

No separate command is needed. The store starts automatically with the backend. No setup is required.
