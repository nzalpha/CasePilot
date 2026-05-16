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

## Phase 6 — Customer Reply Handling & Self-Learning

Phase 6 adds a second polling loop called `reply_poll_loop`. It checks Salesforce cases that are already `In Progress`. These are cases where the agent already answered or flagged the case, and now the system is waiting for the customer to reply.

Salesforce comments use `IsPublished=True` for public customer-visible comments. NawazIdea uses this to separate customer replies from internal AI notes. Internal notes are ignored by the reply handler.

`CasePilot1_LastReplyChecked_c__c` stores the last time NawazIdea checked a case for replies. This helps the system only process new customer comments. After each check, the field is updated.

GPT classifies each customer reply into one of three intents:

- `SATISFIED` means the customer says the issue is fixed or asks to close the case.
- `STUCK` means the customer says the fix did not work or asks a new question.
- `UNCLEAR` means the system cannot tell what the customer means.

For `SATISFIED`, the case is closed. The question and answer are cleaned before learning. PII means private personal information, such as names, emails, phone numbers, or company names. GPT removes PII before the clean Q&A is ingested into Neo4j.

For `SATISFIED`, NawazIdea also creates a Salesforce Knowledge Article as a draft. A draft means an engineer can review it before publishing. This keeps humans in control of new knowledge.

For `STUCK`, NawazIdea runs retrieval again with the latest customer reply. If confidence is high, it posts a new answer. If confidence is low, it flags the case again and sends a Webex alert.

For `UNCLEAR`, NawazIdea sends a Webex alert so an engineer can read the reply manually.

`SELF_LEARNING_ENABLED` controls whether resolved Q&A is added back into the knowledge base. Set it to `false` to stop self-learning while keeping reply handling on.

New `.env` variables:

```env
REPLY_POLL_INTERVAL=60
SELF_LEARNING_ENABLED=true
```
