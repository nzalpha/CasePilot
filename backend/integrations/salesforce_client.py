from __future__ import annotations

import logging

import httpx

from backend.config import settings

try:
    from simple_salesforce import Salesforce
except ImportError:
    Salesforce = None


logger = logging.getLogger(__name__)


# Salesforce must have this custom field before polling works:
# Setup -> Object Manager -> Case -> Fields & Relationships ->
# New -> Checkbox -> Field Name: CasePilot1_Processed__c ->
# Default value: False -> Save


def build_answer_comment(answer: str, sources: list[str], confidence: float) -> str:
    source_lines = "\n".join(sources)
    return f"""[NawazIdea - Automated Response]
Confidence: {confidence:.0%}

{answer}

Sources:
{source_lines}
"""


def build_flag_comment(confidence: float, question: str) -> str:
    return f"""[NawazIdea - Human Review Required]
Confidence score {confidence:.0%} is below threshold.
Question: {question}
Please review and respond manually.
"""


class SalesforceClient:
    def __init__(self) -> None:
        self.sf = None
        required_settings = [
            settings.salesforce_client_id,
            settings.salesforce_client_secret,
            settings.salesforce_instance_url,
        ]
        if any(not value for value in required_settings):
            logger.warning("Salesforce settings are incomplete; integration is disabled")
            return
        if Salesforce is None:
            logger.warning("simple-salesforce is not installed; integration is disabled")
            return

        try:
            token_response = self._get_access_token()
            self.sf = Salesforce(
                instance_url=token_response["instance_url"],
                session_id=token_response["access_token"],
            )
        except Exception as exc:
            logger.exception("Failed to connect to Salesforce: %s", exc)
            self.sf = None

    def _get_access_token(self) -> dict:
        response = httpx.post(
            f"{settings.salesforce_instance_url.rstrip('/')}/services/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.salesforce_client_id,
                "client_secret": settings.salesforce_client_secret,
            },
            timeout=30.0,
        )
        if not response.is_success:
            logger.error("Salesforce token error: %s", response.text)
        response.raise_for_status()
        return response.json()

    def get_new_cases(self) -> list[dict]:
        if self.sf is None:
            return []

        query = """
        SELECT Id, Subject, Description, Status, CaseNumber
        FROM Case
        WHERE Status = 'New'
        AND CasePilot1_Processed__c = false
        ORDER BY CreatedDate ASC
        LIMIT 10
        """
        try:
            result = self.sf.query(query)
            records = result.get("records", [])
            return [
                {
                    "case_id": record.get("Id", ""),
                    "case_number": record.get("CaseNumber", ""),
                    "subject": record.get("Subject", "") or "",
                    "description": record.get("Description", "") or "",
                    "status": record.get("Status", "") or "",
                }
                for record in records
            ]
        except Exception as exc:
            logger.exception("Failed to fetch new Salesforce cases: %s", exc)
            return []

    def post_answer_to_case(
        self,
        case_id: str,
        answer: str,
        sources: list[str],
        confidence: float,
    ) -> bool:
        if self.sf is None:
            return False

        try:
            self.sf.CaseComment.create(
                {
                    "ParentId": case_id,
                    "CommentBody": build_answer_comment(answer, sources, confidence),
                    "IsPublished": False,
                }
            )
            self.sf.Case.update(
                case_id,
                {
                    "Status": "In Progress",
                    "CasePilot1_Processed__c": True,
                },
            )
            return True
        except Exception as exc:
            logger.exception("Failed to post answer to Salesforce case %s: %s", case_id, exc)
            return False

    def flag_for_human_review(
        self,
        case_id: str,
        confidence: float,
        question: str,
    ) -> bool:
        if self.sf is None:
            return False

        try:
            self.sf.CaseComment.create(
                {
                    "ParentId": case_id,
                    "CommentBody": build_flag_comment(confidence, question),
                    "IsPublished": False,
                }
            )
            self.sf.Case.update(
                case_id,
                {
                    "Status": "In Progress",
                    "CasePilot1_Processed__c": True,
                    "Priority": "High",
                },
            )
            return True
        except Exception as exc:
            logger.exception(
                "Failed to flag Salesforce case %s for human review: %s",
                case_id,
                exc,
            )
            return False

    def get_inprogress_cases(self) -> list[dict]:
        if self.sf is None:
            return []

        query = """
        SELECT Id, CaseNumber, Subject, Description, Status,
               CasePilot1_LastReplyChecked_c__c
        FROM Case
        WHERE Status = 'In Progress'
        AND CasePilot1_Processed__c = true
        ORDER BY LastModifiedDate ASC
        LIMIT 20
        """
        try:
            result = self.sf.query(query)
            records = result.get("records", [])
            return [
                {
                    "case_id": record.get("Id", ""),
                    "case_number": record.get("CaseNumber", ""),
                    "subject": record.get("Subject", "") or "",
                    "description": record.get("Description", "") or "",
                    "last_reply_checked": record.get(
                        "CasePilot1_LastReplyChecked_c__c"
                    ),
                }
                for record in records
            ]
        except Exception as exc:
            logger.exception("Failed to fetch in-progress Salesforce cases: %s", exc)
            return []

    def get_new_customer_replies(
        self,
        case_id: str,
        since_iso: str | None,
    ) -> list[str]:
        if self.sf is None:
            return []

        escaped_case_id = case_id.replace("'", "\\'")
        query = f"""
        SELECT CommentBody, CreatedDate
        FROM CaseComment
        WHERE ParentId = '{escaped_case_id}'
        ORDER BY CreatedDate ASC
        """
        try:
            result = self.sf.query(query)
            records = result.get("records", [])
            replies: list[str] = []
            for record in records:
                comment_body = record.get("CommentBody", "") or ""
                # Skip comments posted by the AI system
                if comment_body.startswith("[NawazIdea"):
                    continue
                created_at = record.get("CreatedDate")
                if since_iso and created_at and created_at <= since_iso:
                    continue
                if comment_body:
                    replies.append(comment_body)
            return replies
        except Exception as exc:
            logger.exception("Failed to fetch customer replies for case %s: %s", case_id, exc)
            return []

    def close_case(self, case_id: str) -> bool:
        if self.sf is None:
            return False

        try:
            self.sf.Case.update(case_id, {"Status": "Closed"})
            self.sf.CaseComment.create(
                {
                    "ParentId": case_id,
                    "CommentBody": (
                        "[NawazIdea] This case has been automatically closed "
                        "based on customer confirmation. Thank you!"
                    ),
                    "IsPublished": True,
                }
            )
            return True
        except Exception as exc:
            logger.exception("Failed to close Salesforce case %s: %s", case_id, exc)
            return False

    def create_knowledge_article(self, title: str, summary: str, body: str) -> str | None:
        """Create a draft Knowledge Article. Returns the article ID on success, None on failure."""
        if self.sf is None:
            return None

        import re
        url_name = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-")[:80]

        try:
            result = self.sf.Knowledge__kav.create(
                {
                    "Title": title,
                    "UrlName": url_name,
                    "Summary": summary,
                    "Body__c": body,
                    "IsVisibleInCsp": False,
                    "IsVisibleInPkb": False,
                    "IsVisibleInPrm": False,
                }
            )
            return result.get("id")
        except Exception as exc:
            logger.exception("Failed to create Salesforce knowledge article: %s", exc)
            return None

    def get_case_history(self, case_id: str) -> list[dict]:
        """Return all comments on a case with body and who posted it (AI or customer)."""
        if self.sf is None:
            return []

        escaped_case_id = case_id.replace("'", "\\'")
        query = f"""
        SELECT CommentBody, CreatedDate, IsPublished
        FROM CaseComment
        WHERE ParentId = '{escaped_case_id}'
        ORDER BY CreatedDate ASC
        """
        try:
            result = self.sf.query(query)
            records = result.get("records", [])
            history = []
            for record in records:
                body = record.get("CommentBody", "") or ""
                role = "ai" if body.startswith("[NawazIdea") else "customer"
                history.append({"role": role, "body": body})
            return history
        except Exception as exc:
            logger.exception("Failed to fetch case history for %s: %s", case_id, exc)
            return []

    def update_last_reply_checked(self, case_id: str, timestamp_iso: str) -> bool:
        if self.sf is None:
            return False

        try:
            self.sf.Case.update(
                case_id,
                {"CasePilot1_LastReplyChecked_c__c": timestamp_iso},
            )
            return True
        except Exception as exc:
            logger.exception(
                "Failed to update last reply check time for case %s: %s",
                case_id,
                exc,
            )
            return False
