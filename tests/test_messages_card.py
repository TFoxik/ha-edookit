from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Callable, Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest
from pyedookit import PORTAL_TZ, MessageSummary

from custom_components.edookit.messages_payload import summary_payload

CARD_JS = (
    Path(__file__).parent.parent / "custom_components/edookit/frontend/edookit-messages-card.js"
)
HARNESS_JS = Path(__file__).parent / "messages_card_harness.js"
ENTITY = "sensor.edookit_x_unread_messages"
# Deliberately not the messages' default date, and not the real today.
TODAY = date(2026, 11, 5)


def _summary(
    message_id: int,
    unread: bool = False,
    sent: datetime = datetime(2026, 10, 21, 8, 12, tzinfo=PORTAL_TZ),
    sender: str = "Učitelka A",
) -> MessageSummary:
    return MessageSummary(
        id=message_id,
        subject=f"Zpráva {message_id}",
        sender=sender,
        sent=sent,
        preview="Vážení rodiče…",
        unread=unread,
    )


def _message(body: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": 9003,
        "subject": "Zpráva 9003",
        "sender": "Učitelka A",
        "recipients": "Rodič B",
        "sent": "2026-10-21T08:12:00+02:00",
        "body": body,
        "text": "",
    }


BODY = [
    {
        "tag": "p",
        "children": [
            {"text": "Schůzky "},
            {"tag": "strong", "children": [{"text": "4. 11. od 17:00"}]},
            {"text": " "},
            {"tag": "a", "href": "https://example.org/x", "children": [{"text": "odkaz"}]},
        ],
    }
]


def _render(
    config: dict[str, Any] | None = None,
    summaries: list[MessageSummary] | None = None,
    *,
    payload: dict[str, Any] | None = None,
    ws: dict[str, Any] | None = None,
    clicks: list[str] | None = None,
    language: str = "cs",
) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    if payload is None:
        payload = summary_payload(
            summaries if summaries is not None else [_summary(9003, True)], TODAY
        )
    stdin = json.dumps(
        {
            "config": {"entity": ENTITY, **(config or {})},
            "language": language,
            "events": [payload],
            "ws": ws or {},
            "clicks": clicks or [],
        }
    )
    result = subprocess.run(
        [node, str(HARNESS_JS)], input=stdin, capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def _walk(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield node
    for child in node.get("children", []):
        yield from _walk(child)


def _find(out: dict[str, Any], pred: Callable[[dict[str, Any]], bool]) -> list[dict[str, Any]]:
    return [n for n in _walk(out["tree"]) if pred(n)]


def _cls(name: str) -> Callable[[dict[str, Any]], bool]:
    return lambda n: name in (n.get("cls") or "").split()


def _text(node: dict[str, Any]) -> str:
    return "".join(n.get("text") or "" for n in _walk(node))


def test_card_script_is_valid_javascript() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    subprocess.run([node, "--check", str(CARD_JS)], check=True)


def test_card_never_uses_html_injection() -> None:
    source = CARD_JS.read_text()
    assert not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write", source)


@pytest.mark.parametrize(
    ("unread", "badge"), [(1, "1 nepřečtená"), (2, "2 nepřečtené"), (5, "5 nepřečtených")]
)
def test_header_shows_czech_unread_badge(unread: int, badge: str) -> None:
    out = _render(summaries=[_summary(9000 + i, True) for i in range(unread)])

    assert [_text(n) for n in _find(out, _cls("badge"))] == [badge]
    assert [_text(n) for n in _find(out, _cls("title"))] == ["Zprávy"]


def test_no_badge_when_all_read() -> None:
    out = _render(summaries=[_summary(9003)])

    assert _find(out, _cls("badge")) == []


def test_lists_at_most_max_messages() -> None:
    out = _render({"max_messages": 3}, [_summary(9000 + i) for i in range(12)])

    assert [n["attrs"]["data-id"] for n in _find(out, _cls("row"))] == ["9000", "9001", "9002"]


def test_lists_five_messages_by_default() -> None:
    out = _render(summaries=[_summary(9000 + i) for i in range(12)])

    assert len(_find(out, _cls("row"))) == 5


def test_unread_row_is_marked() -> None:
    out = _render(summaries=[_summary(9003, True), _summary(9002)])

    rows = _find(out, _cls("row"))
    assert [_cls("unread")(r) for r in rows] == [True, False]
    assert "Zpráva 9003" in _text(rows[0])
    assert "Učitelka A" in _text(rows[0])
    assert "21. 10. 8:12" in _text(rows[0])


def test_inline_open_renders_the_body_inside_the_card() -> None:
    out = _render(ws={"9003": _message(BODY)}, clicks=["row:9003"])

    assert out["calls"] == [
        {"type": "edookit/messages/get", "entity_id": ENTITY, "message_id": 9003}
    ]
    assert _find(out, _cls("overlay")) == []
    bodies = _find(out, _cls("message"))
    assert len(bodies) == 1
    strong = [n for n in _walk(bodies[0]) if n["tag"] == "strong"]
    assert [_text(n) for n in strong] == ["4. 11. od 17:00"]
    assert "Rodič B" in _text(bodies[0])


def test_inline_tap_again_collapses() -> None:
    out = _render(ws={"9003": _message(BODY)}, clicks=["row:9003", "row:9003"])

    assert _find(out, _cls("message")) == []


def test_popup_open_renders_the_body_in_a_dialog() -> None:
    out = _render({"open": "popup"}, ws={"9003": _message(BODY)}, clicks=["row:9003"])

    overlays = _find(out, _cls("overlay"))
    assert len(overlays) == 1
    dialog = [n for n in _walk(overlays[0]) if n.get("attrs", {}).get("role") == "dialog"]
    assert len(dialog) == 1
    assert "4. 11. od 17:00" in _text(dialog[0])


def test_popup_closes_with_the_close_button() -> None:
    out = _render({"open": "popup"}, ws={"9003": _message(BODY)}, clicks=["row:9003", "close"])

    assert _find(out, _cls("overlay")) == []


def test_link_opens_in_a_new_tab_safely() -> None:
    out = _render(ws={"9003": _message(BODY)}, clicks=["row:9003"])

    links = _find(out, lambda n: n["tag"] == "a")
    assert [n["attrs"] for n in links] == [
        {"href": "https://example.org/x", "target": "_blank", "rel": "noopener noreferrer"}
    ]


def test_unknown_node_tags_render_as_text_only() -> None:
    body = [{"tag": "script", "children": [{"text": "alert(1)"}]}]
    out = _render(ws={"9003": _message(body)}, clicks=["row:9003"])

    assert _find(out, lambda n: n["tag"] == "script") == []
    assert "alert(1)" in _text(_find(out, _cls("message"))[0])


def test_link_with_non_http_href_renders_as_text() -> None:
    body = [{"tag": "a", "href": "javascript:alert(1)", "children": [{"text": "x"}]}]
    out = _render(ws={"9003": _message(body)}, clicks=["row:9003"])

    assert _find(out, lambda n: n["tag"] == "a") == []
    assert "x" in _text(_find(out, _cls("message"))[0])


def test_load_error_stays_in_the_card() -> None:
    out = _render(ws={"9003": {"error": {"code": "portal_error"}}}, clicks=["row:9003"])

    assert [_text(n) for n in _find(out, _cls("error"))] == [
        "Zprávu se nepodařilo načíst, zkuste to znovu."
    ]
    assert len(_find(out, _cls("row"))) == 1


def test_unavailable_payload_shows_unavailable() -> None:
    out = _render(payload=summary_payload(None, TODAY))

    assert [_text(n) for n in _find(out, _cls("status"))] == ["Zprávy nejsou dostupné"]


def test_empty_inbox_says_so() -> None:
    out = _render(summaries=[])

    assert [_text(n) for n in _find(out, _cls("status"))] == ["Žádné zprávy"]


def test_english_strings_when_language_en() -> None:
    out = _render(summaries=[_summary(9003, True), _summary(9002, True)], language="en")

    assert [_text(n) for n in _find(out, _cls("title"))] == ["Messages"]
    assert [_text(n) for n in _find(out, _cls("badge"))] == ["2 unread"]
    assert "21 Oct 8:12" in _text(_find(out, _cls("row"))[0])


def test_language_option_overrides_the_user_language() -> None:
    out = _render({"language": "en"}, language="cs")

    assert [_text(n) for n in _find(out, _cls("title"))] == ["Messages"]


def test_without_header_shows_only_the_list() -> None:
    out = _render({"show_header": False})

    assert _find(out, _cls("title")) == []
    assert len(_find(out, _cls("row"))) == 1


@pytest.mark.parametrize(
    "config",
    [
        {"entity": ""},
        {"open": "sideways"},
        {"max_messages": 0},
        {"max_messages": "5"},
        {"style": "fancy"},
    ],
)
def test_invalid_config_is_rejected(config: dict[str, Any]) -> None:
    assert _render(config)["error"] is not None


def test_tapping_a_failed_message_again_retries_instead_of_closing() -> None:
    out = _render(ws={"9003": {"error": {"code": "portal_error"}}}, clicks=["row:9003", "row:9003"])

    assert len(out["calls"]) == 2
    assert len(_find(out, _cls("error"))) == 1


def test_unread_only_lists_only_unread_messages() -> None:
    out = _render(
        {"unread_only": True}, [_summary(9003, True), _summary(9002), _summary(9001, True)]
    )

    assert [n["attrs"]["data-id"] for n in _find(out, _cls("row"))] == ["9003", "9001"]


def test_unread_only_with_nothing_unread_says_so() -> None:
    out = _render({"unread_only": True}, [_summary(9002)])

    assert _find(out, _cls("row")) == []
    assert [_text(n) for n in _find(out, _cls("status"))] == ["Žádné nepřečtené zprávy"]


def test_show_preview_false_hides_the_preview() -> None:
    out = _render({"show_preview": False})

    assert _find(out, _cls("preview")) == []


def test_compact_marks_the_card_compact() -> None:
    assert _find(_render({"compact": True}), _cls("compact"))
    assert not _find(_render(), _cls("compact"))


def test_minimal_row_is_subject_and_short_date() -> None:
    today = _summary(9003, True, datetime(2026, 11, 5, 8, 12, tzinfo=PORTAL_TZ))
    yesterday = _summary(9002, False, datetime(2026, 11, 4, 17, 5, tzinfo=PORTAL_TZ))
    older = _summary(9001, False, datetime(2026, 10, 14, 15, 19, tzinfo=PORTAL_TZ))

    out = _render({"style": "minimal"}, [today, yesterday, older])

    assert _find(out, _cls("style-minimal"))
    assert [_text(r) for r in _find(out, _cls("row"))] == [
        "Zpráva 90038:12",
        "Zpráva 9002včera",
        "Zpráva 900114. 10.",
    ]


def test_minimal_badge_counts_new_messages() -> None:
    unread = [_summary(9000 + i, True) for i in range(2)]

    assert [_text(n) for n in _find(_render({"style": "minimal"}, unread), _cls("badge"))] == [
        "2 nové"
    ]
    out = _render({"style": "minimal"}, unread[:1], language="en")
    assert [_text(n) for n in _find(out, _cls("badge"))] == ["1 new"]


def test_modern_row_has_sender_initials_without_titles() -> None:
    out = _render({"style": "modern"}, [_summary(9003, True, sender="Mgr. Petra Suchánková")])

    assert [_text(n) for n in _find(out, _cls("avatar"))] == ["PS"]
    assert [_text(n) for n in _find(out, _cls("badge"))] == ["1"]
    assert "Mgr. Petra Suchánková" in _text(_find(out, _cls("row"))[0])


def test_every_style_opens_messages_inline() -> None:
    for style in ("classic", "minimal", "modern"):
        out = _render({"style": style}, ws={"9003": _message(BODY)}, clicks=["row:9003"])
        assert len(_find(out, _cls("message"))) == 1, style


def test_refused_open_says_only_admins_can_open_messages() -> None:
    out = _render(ws={"9003": {"error": {"code": "unauthorized"}}}, clicks=["row:9003"])

    assert [_text(n) for n in _find(out, _cls("error"))] == [
        "Zprávy může otevírat jen správce Home Assistantu."
    ]
