from __future__ import annotations

import logging

from backend.config import settings

try:
    from simple_salesforce import Salesforce
except ImportError:
    Salesforce = None


logger = logging.getLogger(__name__)


# Salesforce must have this custom field before polling works:
# Setup -> Object Manager -> Case -> Fields & Relationships ->
# New -> Checkbox -> Field Name: NawazIdea_Processed__c ->
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
            settings.salesforce_username,
            settings.salesforce_password,
            settings.salesforce_security_token,
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
            self.sf = Salesforce(
                username=settings.salesforce_username,
                password=settings.salesforce_password,
                security_token=settings.salesforce_security_token,
                consumer_key=settings.salesforce_client_id,
                consumer_secret=settings.salesforce_client_secret,
                instance_url=settings.salesforce_instance_url,
            )
        except Exception as exc:
            logger.exception("Failed to connect to Salesforce: %s", exc)
            self.sf = None

    def get_new_cases(self) -> list[dict]:
        if self.sf is None:
            return []

        query = """
        SELECT Id, Subject, Description, Status, CaseNumber
        FROM Case
        WHERE Status = 'New'
        AND NawazIdea_Processed__c = false
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
                    "IsPublished": True,
                }
            )
            self.sf.Case.update(
                case_id,
                {
                    "Status": "In Progress",
                    "NawazIdea_Processed__c": True,
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
                    "NawazIdea_Processed__c": True,
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
