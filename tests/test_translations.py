from __future__ import annotations

import json
from pathlib import Path

import pytest

import custom_components.edookit

COMPONENT = Path(custom_components.edookit.__file__).parent


@pytest.mark.parametrize("path", ["strings.json", "translations/en.json", "translations/cs.json"])
def test_parse_error_does_not_blame_the_timetable(path: str) -> None:
    # parse_error fires for the events and payments pages too.
    message = json.loads((COMPONENT / path).read_text())["exceptions"]["parse_error"]["message"]
    assert "timetable" not in message.lower()
    assert "rozvrh" not in message.lower()
