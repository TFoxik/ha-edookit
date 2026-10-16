from __future__ import annotations

from datetime import date, datetime, time, timedelta

from pyedookit import PORTAL_TZ, Lesson, SchoolEvent

from custom_components.edookit.week import (
    WeekLessons,
    build_payload,
    default_week,
    derive_periods,
    monday_of,
    period_of,
    resolve_week,
)
from tests.week_data import FIVE_PERIODS, KAMARAD, VOLNO, this_week

real_next = WeekLessons(
    date(2026, 10, 19),
    [
        Lesson(
            start=datetime(2026, 10, 19, 8, 0, tzinfo=PORTAL_TZ),
            end=datetime(2026, 10, 19, 8, 45, tzinfo=PORTAL_TZ),
            subject="Matematika",
        )
    ],
    FIVE_PERIODS,
)

lessons = [
    Lesson(
        start=datetime(2026, 10, 12, 8, 55, tzinfo=PORTAL_TZ),
        end=datetime(2026, 10, 12, 9, 40, tzinfo=PORTAL_TZ),
        subject="Matematika",
    ),
    Lesson(
        start=datetime(2026, 10, 12, 8, 0, tzinfo=PORTAL_TZ),
        end=datetime(2026, 10, 12, 8, 45, tzinfo=PORTAL_TZ),
        subject="Český jazyk",
    ),
    Lesson(
        start=datetime(2026, 10, 13, 8, 0, tzinfo=PORTAL_TZ),
        end=datetime(2026, 10, 13, 8, 45, tzinfo=PORTAL_TZ),
        subject="Matematika",
    ),
]


def test_weekend_defaults_to_next_week():
    assert default_week(date(2026, 10, 16)) == 0  # Friday
    assert default_week(date(2026, 10, 17)) == 1  # Saturday
    assert default_week(date(2026, 10, 18)) == 1  # Sunday


def test_monday_of_any_weekday():
    assert monday_of(date(2026, 10, 12)) == date(2026, 10, 12)
    assert monday_of(date(2026, 10, 18)) == date(2026, 10, 12)


def test_next_week_is_this_week_moved_forward_seven_days():
    week, projected = resolve_week(date(2026, 10, 19), [this_week])
    assert projected is True
    assert week.monday == date(2026, 10, 19)
    assert week.lessons[0].start == datetime(2026, 10, 19, 8, 0, tzinfo=PORTAL_TZ)
    assert week.lessons[0].end - week.lessons[0].start == timedelta(minutes=45)
    assert week.periods == this_week.periods
    assert this_week.lessons[0].start.date() == date(2026, 10, 12)


def test_a_known_week_is_returned_as_is():
    week, projected = resolve_week(date(2026, 10, 12), [this_week])
    assert projected is False and week is this_week


def test_a_real_next_week_wins_over_projection():
    week, projected = resolve_week(date(2026, 10, 19), [this_week, real_next])
    assert projected is False and week is real_next


def test_projection_skips_a_holiday_week_with_no_lessons():
    holiday = WeekLessons(date(2026, 10, 26), [], this_week.periods)
    week, projected = resolve_week(date(2026, 11, 2), [this_week, holiday])
    assert projected and week.lessons[0].start.date() == date(2026, 11, 2)
    assert week.periods == this_week.periods


def test_a_week_before_everything_known_is_not_projected_backwards():
    assert resolve_week(date(2026, 10, 5), [this_week]) == (None, False)


def test_nothing_known_means_no_week():
    assert resolve_week(date(2026, 10, 19), []) == (None, False)


def test_lesson_off_the_bell_schedule_goes_to_the_nearest_period():
    assert period_of(time(8, 10), FIVE_PERIODS) == 1
    assert period_of(time(10, 0), FIVE_PERIODS) == 3
    assert period_of(time(8, 50), FIVE_PERIODS) == 2
    assert period_of(time(13, 0), FIVE_PERIODS) == 5


def test_periods_derived_when_the_page_has_none():
    assert [(p.number, p.start) for p in derive_periods(lessons)] == [
        (1, time(8, 0)),
        (2, time(8, 55)),
    ]


def test_timed_event_replaces_the_lessons_it_overlaps():
    thursday = build_payload(date(2026, 10, 15), [this_week], [KAMARAD])["weeks"][0]["days"][3]
    ev = thursday["events"][0]
    assert (ev["first_period"], ev["last_period"]) == (3, 4)
    assert [r["subject"] for r in ev["replaces"]] == ["Matematika", "Člověk a jeho svět"]
    assert [ls["replaced_by"] for ls in thursday["lessons"]] == [None, None, "e1", "e1"]


def test_all_day_event_fills_its_day_in_the_projected_week():
    nxt = build_payload(date(2026, 10, 17), [this_week], [VOLNO])["weeks"][1]
    assert nxt["projected"] is True
    thursday = nxt["days"][3]
    assert thursday["events"][0]["all_day"] is True
    assert all(ls["replaced_by"] == "e2" for ls in thursday["lessons"])


def test_multi_day_all_day_event_covers_both_days_inclusive():
    prazdniny = SchoolEvent("e3", "Podzimní prázdniny", date(2026, 10, 29), date(2026, 10, 30))
    days = build_payload(date(2026, 10, 24), [this_week], [prazdniny])["weeks"][1]["days"]
    assert [bool(d["events"]) for d in days] == [False, False, False, True, True]


def test_event_after_school_sits_at_the_edge_and_replaces_nothing():
    late = SchoolEvent(
        "e4",
        "Kroužek",
        datetime(2026, 10, 14, 14, 0, tzinfo=PORTAL_TZ),
        datetime(2026, 10, 14, 16, 0, tzinfo=PORTAL_TZ),
    )
    ev = build_payload(date(2026, 10, 14), [this_week], [late])["weeks"][0]["days"][2]["events"][0]
    assert ev["edge"] == "after" and ev["replaces"] == [] and ev["first_period"] is None


def test_event_before_school_sits_at_the_before_edge():
    early = SchoolEvent(
        "e5",
        "Družina",
        datetime(2026, 10, 14, 7, 0, tzinfo=PORTAL_TZ),
        datetime(2026, 10, 14, 7, 45, tzinfo=PORTAL_TZ),
    )
    ev = build_payload(date(2026, 10, 14), [this_week], [early])["weeks"][0]["days"][2]["events"][0]
    assert ev["edge"] == "before" and ev["replaces"] == []


def test_payload_says_which_week_to_show_and_marks_unloaded_weeks():
    p = build_payload(date(2026, 10, 17), [], [])
    assert p["default_week"] == 1
    assert [w["loaded"] for w in p["weeks"]] == [False, False]


def test_payload_shape_of_a_lesson_and_a_period():
    week = build_payload(date(2026, 10, 15), [this_week], [])["weeks"][0]
    assert week["monday"] == "2026-10-12" and week["loaded"] is True
    assert week["periods"][1] == {"number": 2, "start": "08:55", "end": "09:40"}
    assert week["days"][3]["lessons"][2] == {
        "period": 3,
        "start": "10:00",
        "end": "10:45",
        "code": "M",
        "subject": "Matematika",
        "teacher": "Učitel A",
        "room": "1.B",
        "note": None,
        "changed": False,
        "cancelled": False,
        "replaced_by": None,
    }


def test_event_spanning_midnight_is_clipped_to_each_day():
    camp = SchoolEvent(
        "e6",
        "Škola v přírodě",
        datetime(2026, 10, 14, 20, 0, tzinfo=PORTAL_TZ),
        datetime(2026, 10, 15, 9, 0, tzinfo=PORTAL_TZ),
    )
    days = build_payload(date(2026, 10, 14), [this_week], [camp])["weeks"][0]["days"]
    wed, thu = days[2]["events"][0], days[3]["events"][0]
    assert (wed["start"], wed["edge"]) == ("20:00", "after")
    assert (thu["start"], thu["end"], thu["edge"]) == ("00:00", "09:00", None)
    assert (thu["first_period"], thu["last_period"]) == (1, 2)


def test_unloaded_week_keeps_the_remembered_periods():
    old = WeekLessons(date(2026, 10, 5), [], FIVE_PERIODS)
    payload = build_payload(date(2026, 10, 14), [old], [])
    assert [w["loaded"] for w in payload["weeks"]] == [False, False]
    assert len(payload["weeks"][0]["periods"]) == 5
    assert all(d["lessons"] == [] for d in payload["weeks"][0]["days"])


def test_events_are_sorted_all_day_first_then_by_start():
    late = SchoolEvent(
        "b",
        "B",
        datetime(2026, 10, 15, 14, 0, tzinfo=PORTAL_TZ),
        datetime(2026, 10, 15, 15, 0, tzinfo=PORTAL_TZ),
    )
    all_day = SchoolEvent("a", "A", date(2026, 10, 15), date(2026, 10, 15))
    thursday = build_payload(date(2026, 10, 15), [this_week], [late, KAMARAD, all_day])
    ids = [e["id"] for e in thursday["weeks"][0]["days"][3]["events"]]
    assert ids == ["a", "e1", "b"]
