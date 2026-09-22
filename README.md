# Edookit for Home Assistant

An unofficial custom integration that brings your child's school timetable
from [Edookit](https://edookit.com), the parent portal used by Czech
schools, into Home Assistant. It adds a calendar of the week's lessons,
sensors for the next lesson and today's lesson count, and an event entity
that fires when a lesson is cancelled or changed.

Edookit's official REST API only works if a school administrator enables
it, so this integration signs in the way a parent does, through Plus4U,
and reads the portal pages using the
[pyedookit](https://github.com/tfox/pyedookit) library. Edookit does not
support it, and a change to the portal's pages can break it until
pyedookit is updated.

## Use cases

- Show this week's timetable on a dashboard with the calendar card.
- Get a phone notification when a lesson is cancelled.
- A morning announcement: "You have 5 lessons today, the first is Math in room 12."
- Wake-up or heating automations that depend on whether there is school today.

## Entities

Each configured account gets one **Edookit {school}** service device with
these entities:

| Entity | Example ID | State | Attributes |
|---|---|---|---|
| Timetable (calendar) | `calendar.edookit_zs_example_timetable` | on during a lesson | lessons as events; cancelled/changed ones get `(zrušeno)`/`(změna)` in the title |
| Next lesson (sensor) | `sensor.edookit_zs_example_next_lesson` | subject name | `start`, `end`, `room`, `teacher` |
| Lessons today (sensor) | `sensor.edookit_zs_example_lessons_today` | number of lessons not cancelled | |
| Timetable changed (event) | `event.edookit_zs_example_timetable_changed` | time of last event | `event_type` (`lesson_cancelled` / `lesson_changed`), `subject`, `start`, `room`, `teacher` |

Lessons that were already cancelled when the integration started don't
fire the event; it fires once for each lesson that becomes cancelled or
changed while it's running.

## Installation

### HACS (recommended)

1. In HACS, open the menu → **Custom repositories**, add
   `https://github.com/tfox/ha-edookit` with category **Integration**.
2. Search for **Edookit**, download it, and restart Home Assistant.

### Manual

Copy `custom_components/edookit` into your Home Assistant
`config/custom_components/` directory and restart.

Requires Home Assistant 2025.1 or newer.

## Configuration

Go to **Settings → Devices & services → Add integration → Edookit**:

| Field | Description |
|---|---|
| School subdomain | The part before `.edookit.net`. For `https://zs-example.edookit.net`, enter `zs-example`. |
| Plus4U username or email | The Plus4U account you use to sign in to the parent portal. |
| Plus4U password | Used once to sign in and never stored. |

To follow two children with separate accounts, add the integration once
per account.

## How data is updated

- The timetable is polled every **30 minutes**.
- Edookit's own session lasts about 30–60 minutes. The integration renews it
  silently using the Plus4U sign-in cookie, which lasts about **19 days**.
- When that cookie expires, Home Assistant shows a **reauthentication**
  notification. Enter your password again and the integration carries on.

## Examples

Notify when a lesson is cancelled (replace the IDs with yours):

```yaml
automation:
  - alias: "School: lesson cancelled"
    triggers:
      - trigger: state
        entity_id: event.edookit_zs_example_timetable_changed
    conditions:
      - condition: template
        value_template: "{{ trigger.to_state.attributes.event_type == 'lesson_cancelled' }}"
    actions:
      - action: notify.mobile_app_my_phone
        data:
          title: "Lesson cancelled"
          message: >-
            {{ trigger.to_state.attributes.subject }} at
            {{ as_timestamp(trigger.to_state.attributes.start) | timestamp_custom('%H:%M') }}
```

Morning summary on school days:

```yaml
automation:
  - alias: "School: morning summary"
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
            first up: {{ states('sensor.edookit_zs_example_next_lesson') }}
            in {{ state_attr('sensor.edookit_zs_example_next_lesson', 'room') }}.
```

## Known limitations

- **Timetable only.** Grades, homework and exams, the messages inbox,
  attendance and payments are not supported yet.
- **Current week only.** The portal's "next week" navigation hasn't been
  worked out yet. A school's timetable is usually the same every week, so
  this rarely matters.
- **Cancelled/changed lessons are not verified against real data.** The
  markup for them hasn't been seen on a real portal yet, so the event entity
  and the `(zrušeno)`/`(změna)` markers may not fire until it has.
- **Plus4U sign-in only.** Google and local Edookit accounts are not
  supported.
- **It reads the portal's web pages.** When Edookit changes its pages the
  integration can stop updating until pyedookit is fixed. For the same
  reason it can't be added to Home Assistant core, which does not accept
  integrations that scrape websites.

## Troubleshooting

- **"Could not reach Edookit or Plus4U"** during setup: check the school
  subdomain by opening `https://<subdomain>.edookit.net` in a browser.
- **Invalid username or password**: make sure you can sign in to the portal
  with the same Plus4U account in a browser.
- **Entities are unavailable**: the log says why, for example the portal is
  unreachable or the timetable page could not be read. If the page could not
  be read, the portal has probably changed; please open an issue.
- **Debug logging**: add this to `configuration.yaml` and restart:

  ```yaml
  logger:
    logs:
      custom_components.edookit: debug
      pyedookit: debug
  ```

- **Diagnostics**: on the Edookit device page, choose **Download
  diagnostics** and attach the file to your issue. The session and school
  are redacted.

## Removal

1. **Settings → Devices & services → Edookit**, open the entry's menu and
   choose **Delete**.
2. If installed through HACS, remove **Edookit** in HACS and restart Home
   Assistant. For a manual install, delete `custom_components/edookit`.

Nothing is stored outside Home Assistant's config entry, and the password
was never stored.

## Development

Requires a local checkout of [pyedookit](https://github.com/tfox/pyedookit)
next to this repository until it is published to PyPI:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ../pyedookit
pip install -e ".[test]"
pytest
ruff check .
mypy custom_components
```

Progress against Home Assistant's
[Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
is tracked in `custom_components/edookit/quality_scale.yaml`. `hassfest` and
HACS validation run in CI (`.github/workflows/`).
