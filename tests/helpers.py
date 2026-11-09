from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from pyedookit import Lesson, Period, TimetableWeek


def week(lessons: list[Lesson], periods: list[Period] | None = None) -> TimetableWeek:
    return TimetableWeek(lessons=lessons, periods=periods or [])


def run_node(harness: Path, payload: dict[str, Any], tz: str | None = None) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    result = subprocess.run(
        [node, str(harness)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
        env={**os.environ, **({"TZ": tz} if tz else {})},
    )
    return json.loads(result.stdout)


def walk(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield node
    for child in node.get("children", []):
        yield from walk(child)


def text(node: dict[str, Any]) -> str:
    return "".join(n["text"] for n in walk(node) if n["tag"] == "#text")


def find(node: dict[str, Any], pred: Callable[[dict[str, Any]], bool]) -> list[dict[str, Any]]:
    return [n for n in walk(node) if pred(n)]
