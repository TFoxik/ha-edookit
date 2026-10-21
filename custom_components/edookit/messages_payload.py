from __future__ import annotations

from datetime import date
from typing import Any

from pyedookit import Message, MessageSummary


def summary_payload(summaries: list[MessageSummary] | None, today: date) -> dict[str, Any]:
    if summaries is None:
        return {"messages": [], "unread": 0, "available": False, "today": today.isoformat()}
    return {
        "today": today.isoformat(),
        "messages": [
            {
                "id": s.id,
                "subject": s.subject,
                "sender": s.sender,
                "sent": s.sent.isoformat(),
                "preview": s.preview,
                "unread": s.unread,
            }
            for s in summaries
        ],
        "unread": sum(s.unread for s in summaries),
        "available": True,
    }


def message_payload(message: Message) -> dict[str, Any]:
    return {
        "id": message.id,
        "subject": message.subject,
        "sender": message.sender,
        "recipients": message.recipients,
        "sent": message.sent.isoformat(),
        "body": message.body,
        "text": message.body_text,
    }
