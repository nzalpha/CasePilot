# Agents Folder

## What This Folder Does

This folder runs the background agent (code that works quietly while the server is running). The agent checks Salesforce for new cases, sends each case question to the retrieval API, and chooses what to do with the answer. It either posts the answer back to Salesforce or asks a human to review the case.

## What Each File Does

- `case_listener.py` polls Salesforce, calls the retrieval API, and sends each case to the right decision path.
- `agent_decision.py` contains the two decisions the agent can make: answer automatically or flag for human review.
- `__init__.py` tells Python that this folder is a package (a folder of Python code that can be imported).

## SUMMARY

The agent starts when the backend starts.
It checks Salesforce every few seconds.
It sends new case questions to NawazIdea retrieval.
It checks the confidence score.
High-confidence answers are posted to Salesforce.
Low-confidence cases are sent to a human.
