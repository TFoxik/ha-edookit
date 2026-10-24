from __future__ import annotations

from datetime import date
from typing import Any

from pyedookit import Grades


def grades_payload(
    grades: Grades | None, today: date, seen: frozenset[int] = frozenset()
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "available": grades is not None,
        "today": today.isoformat(),
        "term": None,
        "grades": [],
        "subjects": [],
    }
    if grades is None:
        return payload
    payload["term"] = grades.term
    payload["grades"] = [
        {
            "id": g.id,
            "mark": g.mark,
            "value": g.value,
            "weight": g.weight,
            "topic": g.topic,
            "category": g.category,
            "teacher": g.teacher,
            "entered": g.entered.isoformat(),
            "course_id": g.course_id,
            "subject": g.subject,
            "short": g.short,
            "seen": g.id in seen,
        }
        for g in grades.grades
    ]
    payload["subjects"] = [
        {
            "course_id": s.course_id,
            "name": s.name,
            "short": s.short,
            "teacher": s.teacher,
            "attendance": s.attendance_percent,
            "average": grades.average(s.course_id),
            "marks": [
                {"mark": g.mark, "value": g.value}
                for g in reversed(grades.for_subject(s.course_id))
            ],
        }
        for s in grades.subjects
    ]
    return payload
