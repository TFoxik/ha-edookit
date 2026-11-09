from __future__ import annotations

from typing import Any

from pyedookit import Homework


def homework_payload(items: list[Homework] | None) -> dict[str, Any]:
    if items is None:
        return {"available": False, "homework": []}
    return {
        "available": True,
        "homework": [
            {
                "id": item.id,
                "title": item.title,
                "text": item.text,
                "subject": item.subject,
                "short": item.short,
                "code": item.code,
                "group": item.group,
                "teacher": item.teacher,
                "due": item.due.isoformat() if item.due else None,
                "done": item.done,
            }
            for item in items
        ],
    }
