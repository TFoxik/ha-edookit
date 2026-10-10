# Edookit for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![Release](https://img.shields.io/github/v/release/TFoxik/ha-edookit)](https://github.com/TFoxik/ha-edookit/releases)
[![Tests](https://github.com/TFoxik/ha-edookit/actions/workflows/test.yml/badge.svg)](https://github.com/TFoxik/ha-edookit/actions/workflows/test.yml)

An unofficial integration that brings your child's school timetable, school
events and payments from [Edookit](https://edookit.com), the parent portal
used by Czech schools, into Home Assistant.

Edookit's REST API only works if a school administrator enables it, so the
integration signs in like a parent does, through Plus4U, and reads the portal
pages using [pyedookit](https://github.com/TFoxik/pyedookit). Edookit doesn't
support it, and a change to the portal can break it until pyedookit is
updated.

## Entities

Each account gets one **Edookit {school}** device:

| Entity | State | Attributes |
|---|---|---|
| Timetable (calendar) | on during a lesson | this week's lessons; cancelled/changed ones get `(zrušeno)`/`(změna)` in the title |
| Next lesson (sensor) | subject | `start`, `end`, `room`, `teacher` |
| Lessons today (sensor) | lessons that aren't cancelled | |
| Timetable changed (event) | time of the last change | `event_type` (`lesson_cancelled`/`lesson_changed`), `subject`, `start`, `room`, `teacher` |
| School events (calendar) | on during an event | trips, holidays and events from "Mé budoucí události" |
| Payments due (sensor) | amount still to pay, in CZK | `paid`, `overpaid`, `unpaid_requests` |

Entity IDs look like `sensor.edookit_<school>_next_lesson`. The event fires
for lessons that become cancelled or changed while Home Assistant is
running.

## Installation

Requires Home Assistant 2026.9 or newer.

1. In HACS, open ⋮ → **Custom repositories** and add
   `https://github.com/TFoxik/ha-edookit` as an **Integration**.
2. Download **Edookit** and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → Edookit** and
   enter:
   - **School subdomain**: for `https://zs-example.edookit.net`, enter
     `zs-example`.
   - **Plus4U username/email and password**: the account you use for the
     parent portal. The password is used once to sign in and is never stored.

Add the integration once per account to follow several children. For a
manual install, copy `custom_components/edookit` into your
`config/custom_components/` and restart.

## How it updates

- The timetable updates every 30 minutes; events and payments every 3 hours.
  If only the events or payments page fails, only those entities become
  unavailable.
- The portal session is renewed silently using the Plus4U sign-in, which
  lasts about 19 days. After that Home Assistant asks you to sign in again.

## Examples

Notify when a lesson is cancelled:

```yaml
triggers:
  - trigger: state
    entity_id: event.edookit_zs_example_timetable_changed
conditions:
  - "{{ trigger.to_state.attributes.event_type == 'lesson_cancelled' }}"
actions:
  - action: notify.mobile_app_my_phone
    data:
      title: Lesson cancelled
      message: >-
        {{ trigger.to_state.attributes.subject }} at
        {{ as_timestamp(trigger.to_state.attributes.start) | timestamp_custom('%H:%M') }}
```

Morning summary on school days:

```yaml
triggers:
  - trigger: time
    at: "06:45:00"
conditions:
  - condition: numeric_state
    entity_id: sensor.edookit_zs_example_lessons_today
    above: 0
actions:
  - action: notify.mobile_app_my_phone
    data:
      message: >-
        {{ states('sensor.edookit_zs_example_lessons_today') }} lessons today,
        first {{ states('sensor.edookit_zs_example_next_lesson') }}
        in room {{ state_attr('sensor.edookit_zs_example_next_lesson', 'room') }}.
```

## Limitations

- **Supported:** timetable, school events and payments. Grades, attendance,
  homework, tests, messages and consents are not.
- **Current week only:** the portal's next-week navigation hasn't been worked
  out. School timetables rarely change week to week.
- **Not yet seen on a real portal:** cancelled or changed lessons, and unpaid
  payment requests. The cancellation markers and event may not fire until
  pyedookit has real examples. The payments total is still right, because it
  comes from the portal's own summary.
- **Plus4U accounts only:** Google and local Edookit sign-ins aren't
  supported.

## Privacy

- The password is never stored. The config entry holds the portal session
  cookies, as any Home Assistant integration with a login does.
- Payment request titles (`unpaid_requests`) aren't written to the recorder's
  history.
- Diagnostics redact the session and the school.

### Page capture (off by default)

**Configure** on the integration has one option: **Save pages with new
content for development**. It watches the homework, tests, messages and
consents pages, which have no entities yet. When one of them changes, it
saves the page to `config/edookit_captures/` (readable only by the owner) and
shows a notification.

Sharing such a file in an issue, with names removed, lets support for that
page be built. The files contain personal data, so leave the option off
unless you want to help.

## Troubleshooting

- **"Invalid username or password"** can also mean a wrong school subdomain.
  Check that `https://<subdomain>.edookit.net` opens in a browser, and that
  you can sign in there with the same Plus4U account.
- **Entities unavailable:** the log says why. "Page could not be read" errors
  usually mean the portal changed; please
  [open an issue](https://github.com/TFoxik/ha-edookit/issues) with the
  device's **Download diagnostics** file attached.
- **Debug logging:**

  ```yaml
  logger:
    logs:
      custom_components.edookit: debug
      pyedookit: debug
  ```

## Removal

Delete the entry in **Settings → Devices & services → Edookit**, then remove
**Edookit** in HACS and restart. If page capture was on, also delete
`config/edookit_captures/`.

## Development

Needs Python 3.14 and [uv](https://docs.astral.sh/uv/). Install only the
dependencies, not the repo itself: an editable install adds a path hook that
Home Assistant's custom-integration loader trips over.

```bash
uv venv -p 3.14 && source .venv/bin/activate
uv pip install -r pyproject.toml --extra test
uv pip install -e ../pyedookit  # optional: a local pyedookit checkout
pytest && ruff check . && mypy custom_components
```

`scripts/dev-ha.sh start` runs a local Home Assistant with the integration
loaded from the working copy. Progress against the
[Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
is tracked in `custom_components/edookit/quality_scale.yaml`.
