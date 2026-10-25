from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

FRONTEND = Path(__file__).parent.parent / "custom_components/edookit/frontend"
HARNESS_JS = Path(__file__).parent / "font_sizes_harness.js"
CARDS = ["edookit-timetable-card", "edookit-messages-card", "edookit-grades-card"]
SCALE = {"title": "16px", "text": "14px", "meta": "12px", "min": "11px"}
# Tile glyphs and the big grade mark are sized to their boxes, not to the text scale.
DISPLAY_SIZES = {
    "edookit-timetable-card": ["15px", "20px", "20px", "28px"],
    "edookit-messages-card": [],
    "edookit-grades-card": ["26px"],
}


def _style(card: str) -> str:
    source = (FRONTEND / f"{card}.js").read_text()
    return source[source.index("const STYLE = `") : source.index("`;", source.index("const STYLE"))]


@pytest.mark.parametrize("card", CARDS)
def test_every_card_has_the_same_default_scale(card: str) -> None:
    style = _style(card)
    for step, size in SCALE.items():
        assert f"--t-{step}: var(--edookit-font-{step}, {size});" in style


@pytest.mark.parametrize("card", CARDS)
def test_text_sizes_come_only_from_the_scale(card: str) -> None:
    sizes = re.findall(r"font-size:\s*([^;]+);", _style(card))
    fixed = [size for size in sizes if not size.startswith("var(--t-")]
    assert sorted(fixed) == DISPLAY_SIZES[card]


def _configure(card: str, *configs: dict[str, Any]) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    stdin = json.dumps(
        {
            "script": str(FRONTEND / f"{card}.js"),
            "tag": card,
            "configs": [{"entity": "sensor.edookit_x", **config} for config in configs],
        }
    )
    result = subprocess.run(
        [node, str(HARNESS_JS)], input=stdin, capture_output=True, text=True, check=True, timeout=20
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("card", CARDS)
def test_without_font_sizes_the_card_keeps_the_shared_scale(card: str) -> None:
    assert _configure(card, {}) == {"error": None, "host": {}}


@pytest.mark.parametrize("card", CARDS)
def test_font_sizes_override_this_card_only(card: str) -> None:
    shown = _configure(card, {"font_sizes": {"title": 20, "text": 16.5}})
    assert shown == {"error": None, "host": {"--t-title": "20px", "--t-text": "16.5px"}}


@pytest.mark.parametrize("card", CARDS)
def test_removing_font_sizes_goes_back_to_the_scale(card: str) -> None:
    shown = _configure(card, {"font_sizes": {"meta": 13}}, {})
    assert shown["host"] == {}


@pytest.mark.parametrize(
    ("font_sizes", "error"),
    [
        ([14], "font_sizes must be a map with title, text, meta, min"),
        ({"body": 14}, "font_sizes takes only title, text, meta, min"),
        ({"text": "14px"}, "font_sizes.text must be a number of pixels from 8 to 48"),
        ({"min": 4}, "font_sizes.min must be a number of pixels from 8 to 48"),
    ],
)
@pytest.mark.parametrize("card", CARDS)
def test_card_rejects_bad_font_sizes(card: str, font_sizes: Any, error: str) -> None:
    assert _configure(card, {"font_sizes": font_sizes})["error"] == error
