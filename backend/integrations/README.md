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
