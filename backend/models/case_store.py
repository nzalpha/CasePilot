from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from threading import Lock


@dataclass
class CaseRecord:
    case_id: str
    case_number: str
    subject: str
    question: str
    action: str
    confidence: float
    answer: str | None
    sources: list[str]
    processed_at: str
    status: str


class CaseStore:
    def __init__(self) -> None:
        self._records: dict[str, CaseRecord] = {}
        self._lock = Lock()

    def add(self, record: CaseRecord) -> None:
        with self._lock:
            self._records[record.case_id] = deepcopy(record)

    def get(self, case_id: str) -> CaseRecord | None:
        with self._lock:
            record = self._records.get(case_id)
            return deepcopy(record) if record is not None else None

    def all(self) -> list[CaseRecord]:
        with self._lock:
            records = sorted(
                self._records.values(),
                key=lambda record: record.processed_at,
                reverse=True,
            )
            return deepcopy(records)

    def update_status(self, case_id: str, status: str) -> bool:
        with self._lock:
            record = self._records.get(case_id)
            if record is None:
                return False
            record.status = status
            return True

    def summary(self) -> dict:
        with self._lock:
            records = list(self._records.values())
            return {
                "total": len(records),
                "auto_answered": sum(
                    1 for record in records if record.action == "auto_answered"
                ),
                "flagged_for_human": sum(
                    1 for record in records if record.action == "flagged_for_human"
                ),
                "resolved": sum(1 for record in records if record.status == "resolved"),
                "escalated": sum(1 for record in records if record.status == "escalated"),
            }


case_store = CaseStore()
