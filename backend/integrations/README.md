# Integrations Folder

## 1. What This Folder Does

This folder handles all communication between NawazIdea and Salesforce. Salesforce is the customer support system where cases are stored. The code logs in, fetches new cases, posts answers, and flags cases for humans when the answer is not confident enough.

## 2. What salesforce_client.py Does

`salesforce_client.py` contains the Salesforce client (the code object that talks to Salesforce). It connects to Salesforce, asks for new cases, writes comments on cases, and updates case fields. It keeps all Salesforce-specific code in one place so the rest of the backend can stay simple.

## 3. What Each Method Does

- `__init__` checks the Salesforce settings and connects to Salesforce if everything is filled in.
- `get_new_cases` asks Salesforce for up to 10 new cases that NawazIdea has not processed yet.
- `post_answer_to_case` writes an automated answer on a case and marks that case as processed.
- `flag_for_human_review` writes an internal note for the support team and marks the case as needing human attention.
- `build_answer_comment` formats the public answer that will be posted on a case.
- `build_flag_comment` formats the internal note that tells a human to review the case.

## 4. What The Custom Salesforce Field Is

`NawazIdea_Processed__c` is a custom checkbox field (a true or false field that you add yourself) on the Salesforce Case object. NawazIdea uses it to remember which cases it has already handled. This prevents the same case from being answered again and again.

Create it in Salesforce here:

```text
Setup -> Object Manager -> Case -> Fields & Relationships ->
New -> Checkbox -> Field Name: NawazIdea_Processed__c ->
Default value: False -> Save
```

## 5. What The Comment Formats Look Like

Automated answer comment:

```text
[NawazIdea - Automated Response]
Confidence: 95%

Answer text goes here.

Sources:
https://example.com/source
manual.pdf
```

Human review comment:

```text
[NawazIdea - Human Review Required]
Confidence score 50% is below threshold.
Question: How do I reset a router?
Please review and respond manually.
```

## SUMMARY

NawazIdea logs in to Salesforce.
It looks for new cases that were not processed.
It reads the case subject and description.
It later posts an answer if confidence is high.
It flags the case for a person if confidence is low.
It marks each handled case as processed.
This keeps Salesforce and NawazIdea in sync.

## Phase 5 — Webex Notifications

`WebexClient` sends a Webex message when a Salesforce case needs human review. Webex is the chat tool where engineers can receive alerts. The message gives the engineer the case details and a direct Salesforce link.

The two `.env` variables needed are:

- `WEBEX_BOT_TOKEN` is the secret token for your Webex bot.
- `WEBEX_ROOM_ID` is the ID of the Webex space where messages should be sent.

To create a Webex Bot, go to:

```text
developer.webex.com -> My Webex Apps -> Create a Bot
```

To get the Room ID, add the bot to a Webex space. Then call this Webex API with the bot token:

```text
GET https://webexapis.com/v1/rooms
```

Find the room you want in the response and copy its `id`.

The notification message looks like this:

```text
🚨 NawazIdea — Human Review Required

Case Number: 00012345
Subject: Router reset failed
Confidence Score: 50%
Question: How do I reset my router?
Salesforce Case: clickable Salesforce case link

Please review, edit the AI draft in Salesforce if present, and respond.
```

If Webex is not configured, the system keeps running. It logs a warning and does not send notifications.

## Phase 6 — Salesforce Reply Handling & Knowledge Articles

Phase 6 added four new methods to `salesforce_client.py` and one new integration:

**New methods in salesforce_client.py:**

- `get_inprogress_cases` — fetches all cases with Status = "In Progress" and `CasePilot1_Processed__c = true`. These are cases the system already handled and is now monitoring for customer replies.
- `get_new_customer_replies` — fetches case comments that were not posted by NawazIdea (filters out any comment starting with `[NawazIdea`). Returns only comments posted after the last check timestamp.
- `get_case_history` — fetches all comments on a case and labels each one as "ai" or "customer". Used to build the full context for GPT when writing a knowledge article.
- `close_case` — sets case Status to "Closed" and posts a public closing comment confirming auto-closure.
- `create_knowledge_article` — creates a draft Knowledge Article in Salesforce Knowledge (`Knowledge__kav`) with Title, UrlName, Summary, and Body. The article is internal only (not visible to customers) until an engineer publishes it.
- `update_last_reply_checked` — updates `CasePilot1_LastReplyChecked_c__c` on the case to the current timestamp so the next poll only reads new comments.

**Custom Salesforce fields required:**

| Field | Object | Type | Purpose |
|-------|--------|------|---------|
| `CasePilot1_Processed__c` | Case | Checkbox | Marks cases already handled by NawazIdea |
| `CasePilot1_LastReplyChecked_c__c` | Case | DateTime | Tracks when replies were last checked |
| `Body__c` | Knowledge | Rich Text Area | Stores the article body content |

**New `.env` variables:**
```
REPLY_POLL_INTERVAL=60
SELF_LEARNING_ENABLED=true
```
