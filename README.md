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
| School ends (sensor) | end of today's last lesson that isn't cancelled; unknown on days without lessons | |
| Timetable changed (event) | time of the last change | `event_type` (`lesson_cancelled`/`lesson_changed`), `subject`, `start`, `room`, `teacher` |
| School events (calendar) | on during an event | trips, holidays and events from "Mé budoucí události" |
| Payments due (sensor) | amount still to pay, in CZK | `paid`, `overpaid`, `unpaid_requests` |
| Unread messages (sensor) | unread messages in Schránka | |
| Latest grade (sensor) | the newest grade's mark; unknown before the term's first grade | |

Entity IDs look like `sensor.edookit_<school>_next_lesson`. The event fires
for lessons that become cancelled or changed while Home Assistant is
running.

## Weekly timetable card

The integration ships a Lovelace card that shows the week the way the portal
does: days down the side, lesson periods across the top, with the subject
abbreviation and room in each tile. A school event that replaces lessons is
drawn as one tile over those periods (a trip over periods 3-4), and an
all-day event such as "Ředitelské volno" fills the whole day. An event before
or after school (an evening meeting for parents) gets its own column right
next to the lessons; periods no lesson uses that week are left out on that
side. Tap a tile for the details: teacher, room and "Učivo" for a lesson;
time, the lessons it replaces and the description for an event. The details
pop-up closes by itself after a minute, so a wall tablet is never left
covered.

There is nothing to install: Home Assistant loads the card with the
integration. Add it to a dashboard (reload the browser once after the first
update) from **Add card** → **Edookit timetable** and set it up in the
visual editor, or in YAML:

```yaml
type: custom:edookit-timetable-card
entity: calendar.edookit_zs_example_timetable
title: Anna # optional
language: cs # optional
style: glow # optional; classic (default) or glow
show_room: false # optional
show_header: false # optional
```

| Option | |
|---|---|
| `entity` | Any entity of the Edookit account; the timetable calendar is the usual choice. One card shows one child. |
| `title` | A name shown at the top of the card, before the week's dates, so that with more children you can tell the timetables apart. It stays when `show_header: false` hides the rest of the header. No title by default. |
| `language` | `cs` or `en`. By default the card follows each viewer's Home Assistant language: Czech for `cs`, English for anything else. Subjects, events and teachers are the portal's own text and are never translated. |
| `style` | `classic` (default) draws every lesson and event as a tile. `glow` is for dark dashboards without card boxes: no card background, no tiles, just the subject codes. Only what is happening now glows: the lesson in progress gets an amber halo and today's day name shines. An event is plain text in its colour until it is happening; then it gets a halo in that colour (an all-day event, all day). A changed lesson gets a small glowing dot, and the details open on frosted glass. |
| `show_room` | `false` hides the room on the tiles and shows the subject abbreviation larger, for reading from across a room. The room is still in the details when you tap a lesson. Default `true`. |
| `show_header` | `false` hides the date and the **This week** / **Next week** buttons, leaving just the grid. The card then always shows the automatic week: this week from Monday to Friday, next week from Saturday 00:00. Default `true`. |
| `show_periods` | `false` hides the top row of period numbers and start times. Default `true`. |
| `show_days` | `false` hides the first column of weekdays and dates; today's row is then marked with a faint band instead. Default `true`. |

Events use purple, the colour of the school events calendar. Change it with
the `--edookit-event-color` CSS variable, for example in a theme or a
[card-mod](https://github.com/thomasloven/lovelace-card-mod) style. Everything
else follows the Home Assistant theme. With `style: glow`, two more variables
apply: `--edookit-now-color` for the lesson in progress (default amber,
`--amber-color`), and `--edookit-glow-color` for today's day
name and the selected week (default `--primary-color`). Glow needs no
card-mod to drop the card background.

The card shows this week, Monday to Friday, and switches to next week from
Saturday 00:00 (Europe/Prague). **This week** and **Next week** buttons let
you flip by hand; the automatic choice returns at midnight. With
`show_header: false` there are no buttons and the card only follows the
automatic choice.

**Next week is a projection.** The portal's next-week navigation hasn't been
worked out, so until that week starts the card repeats this week's lessons,
with next week's real events on top. A
substitution or cancellation appears only once the week begins. The
Timetable calendar entity never shows projected lessons, so automations are
not affected.

To keep it on a wall tablet next to a calendar, put it in a
[WallCal](https://github.com/TFoxik/wallcal) floating card:

```yaml
type: custom:wallcal-card
entities:
  - calendar.family
overlays:
  - position: bottom-center
    span: 5
    width: 95%
    max_height: 60%
    toggle: pill
    icon: mdi:school
    card:
      type: custom:edookit-timetable-card
      entity: calendar.edookit_zs_example_timetable
```

For a small overlay, `show_header: false`, `show_periods: false` and
`show_days: false` leave only the lesson tiles (and the `title`, if set).

## Messages card

The newest messages from Schránka, with an orange dot on unread ones and the
unread count in the header. Tap a message to read it in full: subject,
sender, recipients, time, and the text with its bold, italics, lists and
links. **Opening a message in Home Assistant marks it read on the portal**,
the same as opening it there.

Add it from **Add card** → **Edookit messages** and set it up in the visual
editor, or in YAML:

```yaml
type: custom:edookit-messages-card
entity: sensor.edookit_zs_example_unread_messages
style: classic      # classic, minimal (one line each) or modern (tiles with initials)
open: inline        # inline (in the card) or popup; default inline
max_messages: 5     # optional; default 5
unread_only: false  # optional; list only unread messages
show_preview: true  # optional; false hides the first line of the text
compact: false      # optional; tighter rows
language: cs        # optional; default = your Home Assistant language
show_header: true   # optional
```

The unread count appears in the header only while something is unread.

Every Home Assistant user who can see the dashboard can open messages, the
same as the other Edookit data. To limit that, turn on **Only administrators
can open messages** under **Configure** on the integration: other users then
still see the list with subjects and previews, but opening a message (its
full text, which also marks it read on the portal) is refused for them. The
card can't enforce this itself; Home Assistant checks it.

Only messages are shown; events, grades and guidance items in Schránka are
not. The text is shown as plain formatted text: images, colours and tables
in a message are dropped, and nothing in a message can run code in Home
Assistant.

## Grades card

The current term's grades. Three views:

- `latest`: the newest grade large (mark, topic, subject, date entered,
  teacher, weight), then the next few.
- `subjects`: one line per subject with its marks (newest on the right, as
  on the portal), the weighted average and attendance.
- `combined`: the newest grade, then only the subjects that have grades;
  subjects without one are folded into a single line.

Grades entered in the last five days carry a "nová" badge until someone
taps the grade; that clears it on every device. The average
counts each grade by its weight; marks that aren't 1–5 are shown but left
out of it. From the second half-year on, only that half-year is shown.

Add it from **Add card** → **Edookit grades** and set it up in the visual
editor, or in YAML:

```yaml
type: custom:edookit-grades-card
entity: sensor.edookit_zs_example_latest_grade
view: combined      # latest, subjects or combined; default combined
max_grades: 5       # optional; grades in the latest view; default 5
language: cs        # optional; default = your Home Assistant language
```

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

- The timetable and the message list update every 30 minutes; events,
  payments and grades every 3 hours. A message's full text is fetched only when you
  open it on the card.
  If only the events, payments or grades pages fail, only those entities
  become unavailable.
- The portal session is renewed silently using the Plus4U sign-in, which is
  set for 30 days. A renewal that fails, for example during a Plus4U or
  portal outage, is retried on the next update; Home Assistant asks you to
  sign in again only when Plus4U requires a new login.

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

- **Supported:** timetable, school events, payments, messages and grades.
  Behaviour notes, homework, tests and consents are not; attendance only as a
  percentage per subject on the grades card.
- **Next week is a copy of this week:** the portal's next-week navigation
  hasn't been worked out, so the card projects it (see
  [Weekly timetable card](#weekly-timetable-card)). Schools that alternate
  between an A and a B week would see the wrong lessons every other week.
- **Not yet seen on a real portal:** cancelled or changed lessons, unpaid
  payment requests, and term or non-numeric grades. The cancellation markers and event may not fire until
  pyedookit has real examples. The payments total is still right, because it
  comes from the portal's own summary.
- **Plus4U accounts only:** Google and local Edookit sign-ins aren't
  supported.

## Privacy

- The password is never stored. The config entry holds the portal session
  cookies, as any Home Assistant integration with a login does.
- Payment request titles (`unpaid_requests`) aren't written to the recorder's
  history. Message subjects and text are never stored in entity states or
  attributes; the card fetches them on demand. The *Latest grade* sensor
  holds only the mark: topics, subjects and teachers stay out of the history.
- Diagnostics redact the session and the school.

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
**Edookit** in HACS and restart. If you turned on page capture in a version
before 0.8.0, also delete `config/edookit_captures/`.

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
loaded from the working copy and the local pyedookit. It also sets
`EDOOKIT_CAPTURE_PAGES=1`, which turns on page capture: once a day the
homework, tests and consents pages, which have no parser yet, are fetched, and
when their content changes the page is saved to `config/edookit_captures/` and
a notification appears. Those files are real markup to build parsers from;
they contain personal data. The switch is not offered to users.

Progress against the
[Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
is tracked in `custom_components/edookit/quality_scale.yaml`.
