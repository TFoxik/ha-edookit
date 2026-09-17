# Edookit for Home Assistant

Unofficial HACS integration for [Edookit](https://edookit.com), the Czech
school parent portal. Built on top of
[pyedookit](https://github.com/tfox/pyedookit), which logs in through
Plus4U (OIDC) and scrapes the portal since Edookit's own REST API is only
enabled per-school by an administrator.

## Status: v0.1.0 - timetable only

- **Calendar** (`calendar.timetable`): this week's and next week's lessons,
  with cancelled/changed lessons flagged in the summary.
- **Sensors**: `sensor.next_lesson` (state = subject, attributes for start,
  end, room, teacher), `sensor.lessons_today` (count).
- **Event** (`event.timetable_changed`): fires `lesson_cancelled` or
  `lesson_changed` the first time a lesson is seen in that state, so an
  automation can trigger once per disruption rather than once per poll.

Not yet implemented: grades, homework/exams, the updates inbox, attendance,
payments, and login via Google or a local Edookit account (only Plus4U is
supported, since that's what pyedookit implements).

## Install

Via [HACS](https://hacs.xyz): add this repository as a custom repository
(category: Integration), then install "Edookit".

Manually: copy `custom_components/edookit` into your Home Assistant's
`custom_components` directory and restart.

Then add the integration from **Settings → Devices & services → Add
integration → Edookit**, and enter your school's subdomain (the part before
`.edookit.net`) and your Plus4U username/email and password.

## How it stays logged in

Edookit's own session lasts roughly 30-60 minutes. This integration refreshes
it silently using the Plus4U cookie (valid roughly 19 days) rather than
storing your password. When that cookie itself expires, Home Assistant will
prompt you to reauthenticate via a notification.

## Development

Requires a local checkout of `pyedookit` (not yet published to PyPI):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ../pyedookit
pip install -e ".[test]"
pytest
ruff check .
mypy custom_components
```

`hassfest` and HACS validation run in CI (`.github/workflows/`).
