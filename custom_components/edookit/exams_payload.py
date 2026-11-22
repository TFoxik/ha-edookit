from __future__ import annotations

from typing import Any

from pyedookit import Exam


def exams_payload(items: list[Exam] | None) -> dict[str, Any]:
    if items is None:
        return {"available": False, "exams": []}
    return {
        "available": True,
        "exams": [
            {
                "id": item.id,
                "title": item.title,
                "subject": item.subject,
                "short": item.short,
                "code": item.code,
                "group": item.group,
                "teacher": item.teacher,
                "kind": item.kind,
                "start": item.start.isoformat(),
                "end": item.end.isoformat(),
            }
            for item in items
        ],
    }
