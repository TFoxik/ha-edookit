# Edookit for Home Assistant

An unofficial custom integration that brings your child's school timetable
from [Edookit](https://edookit.com), the parent portal used by Czech
schools, into Home Assistant. It adds calendars for the week's lessons and for school events, sensors for the next lesson,
today's lesson count and payments due, and an event entity that fires when a lesson is
cancelled or changed.

Edookit's official REST API only works if a school administrator enables
it, so this integration signs in the way a parent does, through Plus4U,
and reads the portal pages using the
[pyedookit](https://github.com/TFoxik/pyedookit) library. Edookit does not
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
| School events (calendar) | `calendar.edookit_zs_example_school_events` | on during an event | school trips, holidays and events from "Mé budoucí události"; all-day events span whole days |
| Payments due (sensor) | `sensor.edookit_zs_example_payments_due` | amount still to pay, in CZK | `paid`, `overpaid`, `unpaid_requests` (title and amount of each unpaid request) |

Lessons that were already cancelled when the integration started don't
fire the event; it fires once for each lesson that becomes cancelled or
changed while it's running.

## Installation

### HACS (recommended)

1. In HACS, open the menu → **Custom repositories**, add
   `https://github.com/TFoxik/ha-edookit` with category **Integration**.
2. Search for **Edookit**, download it, and restart Home Assistant.

### Manual

Copy `custom_components/edookit` into your Home Assistant
`config/custom_components/` directory and restart.

Requires Home Assistant 2026.9 or newer.

## Configuration

Go to **Settings → Devices & services → Add integration → Edookit**:

| Field | Description |
|---|---|
| School subdomain | The part before `.edookit.net`. For `https://zs-example.edookit.net`, enter `zs-example`. |
| Plus4U username or email | The Plus4U account you use to sign in to the parent portal. |
| Plus4U password | Used once to sign in and never stored. |

To follow two children with separate accounts, add the integration once
per account.

### Options

**Settings → Devices & services → Edookit → Configure**:

| Option | Default | Description |
|---|---|---|
| Save pages with new content for development | off | Watches the homework, tests, inbox and consents pages, which aren't supported yet, and saves a copy to `config/edookit_captures/` when their content changes. You get a notification when that happens; sharing the file (with names removed) lets support for that page be built. |

## How data is updated

- The timetable is polled every **30 minutes**; school events and payments every **3 hours**.
  If the events or payments page can't be read, only those entities become unavailable.
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

Notify when the school asks for money:

```yaml
automation:
  - alias: "School: payment due"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.edookit_zs_example_payments_due
        above: 0
    actions:
      - action: notify.mobile_app_my_phone
        data:
          message: >-
            Edookit: {{ states('sensor.edookit_zs_example_payments_due') }} Kč to pay
            ({{ state_attr('sensor.edookit_zs_example_payments_due', 'unpaid_requests')
            | map(attribute='title') | join(', ') }}).
```

## Known limitations

- **Timetable, school events and payments.** Grades, attendance, library and the rest of the
  portal are not supported. Homework, tests, the inbox and consents can be captured for future
  support (see Options), but have no entities yet.
- **Current week only.** The portal's "next week" navigation hasn't been
  worked out yet. A school's timetable is usually the same every week, so
  this rarely matters.
- **Cancelled/changed lessons are not verified against real data.** The
  markup for them hasn't been seen on a real portal yet, so the event entity
  and the `(zrušeno)`/`(změna)` markers may not fire until it has.
- **Unpaid payments are not verified against real data.** Only paid requests have been seen; the
  sensor's state comes from the portal's own "remaining" total, so it is right even if an unpaid
  request isn't listed in `unpaid_requests`.
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

Needs Python 3.14 and [uv](https://docs.astral.sh/uv/). The test dependencies
pin the Home Assistant version the tests run against. Install only the
dependencies, not this repo itself: an editable install adds a path hook that
Home Assistant's custom-integration loader trips over.

```bash
uv venv -p 3.14
source .venv/bin/activate
uv pip install -r pyproject.toml --extra test
uv pip install -e ../pyedookit  # optional: develop against a local pyedookit checkout
pytest
ruff check .
mypy custom_components
```

Progress against Home Assistant's
[Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
is tracked in `custom_components/edookit/quality_scale.yaml`. `hassfest` and
HACS validation run in CI (`.github/workflows/`).
