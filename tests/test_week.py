from __future__ import annotations

from datetime import date, datetime, time, timedelta

from pyedookit import PORTAL_TZ, Lesson

from custom_components.edookit.week import (
    WeekLessons,
    default_week,
    derive_periods,
    monday_of,
    period_of,
    resolve_week,
)
from tests.week_data import FIVE_PERIODS, this_week

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
