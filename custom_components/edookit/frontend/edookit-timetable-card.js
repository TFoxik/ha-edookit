const CARD_TAG = "edookit-timetable-card";
const EDITOR_TAG = "edookit-timetable-card-editor";
const RETRY_MS = 30000;
const DETAIL_TIMEOUT_MS = 60000;
const MINUTE_MS = 60000;
const EDGE_TRACK = "minmax(40px, 0.8fr)";
const STYLES = ["classic", "glow"];
const DEFAULTS = {
  style: "classic",
  show_header: true,
  show_periods: true,
  show_days: true,
  show_room: true,
};
const PRAGUE_CLOCK = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/Prague",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

const STRINGS = {
  cs: {
    thisWeek: "Tento týden",
    nextWeek: "Příští týden",
    notLoaded: "Rozvrh zatím není načten",
    loading: "Načítám…",
    unavailable: "Rozvrh není dostupný, zkouším znovu",
    wholeDay: "Celý den",
    noLessons: "bez výuky",
    tapDetails: "klepněte pro detail",
    close: "Zavřít",
    insteadOf: "Nahrazuje",
    description: "Popis",
    createdBy: "Vytvořil(a)",
    teacher: "Učitel",
    room: "Učebna",
    topic: "Učivo",
    days: ["Po", "Út", "St", "Čt", "Pá"],
    date: (day, month) => `${day}.${month}.`,
  },
  en: {
    thisWeek: "This week",
    nextWeek: "Next week",
    notLoaded: "Timetable not loaded yet",
    loading: "Loading…",
    unavailable: "Timetable unavailable, retrying",
    wholeDay: "Whole day",
    noLessons: "no lessons",
    tapDetails: "tap for details",
    close: "Close",
    insteadOf: "Replaces",
    description: "Description",
    createdBy: "Created by",
    teacher: "Teacher",
    room: "Room",
    topic: "Topic",
    days: ["Mon", "Tue", "Wed", "Thu", "Fri"],
    date: (day, month) =>
      `${day} ${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][month - 1]}`,
  },
};

const STYLE = `
  :host { display: block; position: relative; }
  ha-card { display: block; padding: 12px; }
  .card { container-type: inline-size; color: var(--primary-text-color);
    --ev: var(--edookit-event-color, #7F77DD); }
  .head { display: flex; justify-content: space-between; align-items: center; gap: 8px;
    flex-wrap: wrap; margin-bottom: 8px; }
  .title { font-size: 18px; font-weight: 600; }
  .switch { display: flex; gap: 6px; }
  .switch button { font: inherit; font-size: 12px; padding: 3px 12px; min-height: 36px;
    border-radius: 999px;
    border: 1px solid var(--divider-color); background: none; color: var(--secondary-text-color);
    cursor: pointer; }
  .switch button[aria-pressed="true"] { background: var(--primary-color);
    border-color: var(--primary-color); color: var(--text-primary-color, #fff); }
  .grid { display: grid; --gap: 4px; gap: var(--gap); }
  .period-head { grid-row: 1; align-self: end; font-size: 10px; line-height: 1.2; text-align: center;
    color: var(--secondary-text-color); }
  .period-head b { display: block; font-size: 12px; color: var(--primary-text-color); }
  .day { font-size: 14px; font-weight: 600; line-height: 1.1; padding-top: 6px; }
  .day small { display: block; font-weight: 400; font-size: 10px;
    color: var(--secondary-text-color); }
  .day.today, .day.today small { color: var(--primary-color); }
  .today-row { grid-column: 1 / -1; margin: calc(-1 * var(--gap)); border-radius: 12px;
    background: color-mix(in srgb, var(--primary-color) 18%, transparent);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--primary-color) 55%, transparent); }
  .cell { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .lesson { font: inherit; color: inherit; cursor: pointer; width: 100%; flex: 1; display: flex; flex-direction: column; justify-content: center;
    min-width: 0; min-height: 40px; box-sizing: border-box; padding: 4px 2px; text-align: center;
    border: 1px solid var(--divider-color); border-radius: 8px;
    background: var(--secondary-background-color); }
  .lesson .code { font-size: 20px; font-weight: 500; line-height: 1.15; overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap; }
  .lesson .room { font-size: 10px; color: var(--secondary-text-color); overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap; }
  .lesson.noroom .code { font-size: 28px; }
  .lesson.long .code { font-size: 11px; white-space: normal; overflow-wrap: anywhere;
    hyphens: auto; }
  .lesson.longer .code { font-size: 9px; }
  .lesson.changed { border-color: var(--primary-color); }
  .lesson.cancelled { opacity: 0.55; }
  .lesson.cancelled .code { text-decoration: line-through; }
  .event { font: inherit; color: inherit; cursor: pointer; width: 100%; flex: 1; min-width: 0;
    box-sizing: border-box; display: flex; flex-direction: column; justify-content: center;
    gap: 1px; padding: 5px 6px; text-align: left; border-radius: 8px;
    border: 2px solid var(--ev);
    background: color-mix(in srgb, var(--ev) 14%, var(--card-background-color, #fff)); }
  .event .etitle { font-size: 12px; font-weight: 600; line-height: 1.2; overflow: hidden;
    overflow-wrap: anywhere; display: -webkit-box; -webkit-box-orient: vertical;
    -webkit-line-clamp: 2; line-clamp: 2;
    color: color-mix(in srgb, var(--ev) 55%, var(--primary-text-color)); }
  .event .esub { font-size: 10px; line-height: 1.2;
    color: color-mix(in srgb, var(--ev) 70%, var(--secondary-text-color)); }
  .event.allday { text-align: center; }
  .event.edge { padding: 4px 2px; text-align: center; }
  .event.edge .etitle { font-size: 10px; }
  .event.edge .hint { display: none; }
  .status { font-size: 12px; color: var(--secondary-text-color); margin-top: 4px; }
  @container (max-width: 480px) {
    .title { font-size: 15px; }
    .day { font-size: 12px; }
    .day small { font-size: 9px; }
    .lesson { min-height: 36px; }
    .lesson .code { font-size: 15px; }
    .lesson.noroom .code { font-size: 20px; }
    .lesson .room { font-size: 9px; }
    .lesson.long .code { font-size: 9px; }
    .lesson.longer .code { font-size: 8px; }
    .event .etitle { font-size: 11px; }
    .event .hint { display: none; }
  }
  .overlay { position: absolute; inset: 0; z-index: 1; box-sizing: border-box; padding: 12px;
    display: flex; align-items: center; justify-content: center;
    background: rgba(0, 0, 0, 0.45); border-radius: var(--ha-card-border-radius, 12px); }
  .panel { box-sizing: border-box; width: 100%; max-width: 420px; max-height: 100%;
    overflow: auto; padding: 12px 14px; border-radius: 12px; outline: none;
    border: 1px solid var(--divider-color);
    background: var(--card-background-color, #fff); color: var(--primary-text-color);
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25); font-size: 13px; }
  .panel h4 { margin: 0; font-size: 16px; line-height: 1.25; overflow-wrap: anywhere; }
  .panel .when { margin: 2px 0 8px; color: var(--secondary-text-color); }
  .panel .row { display: flex; gap: 10px; margin: 4px 0; }
  .panel .label { flex: none; width: 84px; color: var(--secondary-text-color); }
  .panel .value { min-width: 0; overflow-wrap: anywhere; white-space: pre-wrap; }
  .panel .close { font: inherit; margin-top: 8px; padding: 0 16px; min-height: 36px;
    border-radius: 999px; cursor: pointer; border: 1px solid var(--primary-color);
    background: var(--primary-color); color: var(--text-primary-color, #fff); }
  ha-card.style-glow { background: none; border: none; box-shadow: none; }
  .style-glow { --now: var(--edookit-now-color, var(--amber-color, #ffc107));
    --glow: var(--edookit-glow-color, var(--primary-color)); }
  .style-glow .switch button { border: none; background: none; }
  .style-glow .switch button[aria-pressed="true"] { background: none; color: var(--glow);
    text-shadow: 0 0 10px color-mix(in srgb, var(--glow) 70%, transparent); }
  .style-glow .day.today, .style-glow .day.today small { color: var(--glow);
    text-shadow: 0 0 10px color-mix(in srgb, var(--glow) 70%, transparent); }
  .style-glow .today-row { box-shadow: none;
    background: radial-gradient(ellipse at center,
      color-mix(in srgb, var(--glow) 14%, transparent), transparent 75%); }
  .style-glow .lesson { position: relative; border: none; border-radius: 10px; background: none;
    transition: box-shadow 0.4s, background-color 0.4s; }
  .style-glow .lesson.now { background: color-mix(in srgb, var(--now) 10%, transparent);
    box-shadow: 0 0 18px 3px color-mix(in srgb, var(--now) 45%, transparent); }
  .style-glow .lesson.changed::after { content: ""; position: absolute; top: 4px; right: 4px;
    width: 6px; height: 6px; border-radius: 50%; background: var(--primary-color);
    box-shadow: 0 0 6px 1px color-mix(in srgb, var(--primary-color) 70%, transparent); }
  .style-glow .event { border: none; background: none; text-align: center; }
  .style-glow .event .etitle { color: var(--ev); }
  .style-glow .event.now { border-radius: 10px;
    background: color-mix(in srgb, var(--ev) 18%, transparent);
    box-shadow: 0 0 18px 4px color-mix(in srgb, var(--ev) 65%, transparent); }
  .style-glow .event .esub { color: var(--secondary-text-color); }
  ha-card.style-glow ~ .overlay { background: none; }
  ha-card.style-glow ~ .overlay .panel {
    border: 1px solid color-mix(in srgb, var(--primary-text-color) 10%, transparent);
    background: color-mix(in srgb, var(--card-background-color, #1c1c1c) 45%, transparent);
    -webkit-backdrop-filter: blur(16px) saturate(140%); backdrop-filter: blur(16px) saturate(140%);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35); }
  ha-card.style-glow ~ .overlay .close { border: none; background: none;
    color: var(--primary-color);
    text-shadow: 0 0 10px color-mix(in srgb, var(--primary-color) 70%, transparent); }
`;

function userLanguage(hass) {
  const locale = hass && hass.locale && hass.locale.language;
  return typeof locale === "string" && locale.startsWith("cs") ? "cs" : "en";
}

function h(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined && text !== null) el.textContent = text;
  return el;
}

function isoParts(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  return { year, month, day };
}

function shiftedDay(iso, days) {
  const { year, month, day } = isoParts(iso);
  const moved = new Date(Date.UTC(year, month - 1, day + days));
  return { month: moved.getUTCMonth() + 1, day: moved.getUTCDate() };
}

function weekTitle(monday) {
  const first = shiftedDay(monday, 0);
  const last = shiftedDay(monday, 4);
  if (first.month === last.month) return `${first.day}.–${last.day}. ${last.month}.`;
  return `${first.day}. ${first.month}.–${last.day}. ${last.month}.`;
}

function shortDate(iso) {
  const { month, day } = isoParts(iso);
  return `${day}.${month}.`;
}

function defaultWeek(payload) {
  return payload.default_week === 1 ? 1 : 0;
}

function clockLabel(hhmm) {
  return hhmm.replace(/^0/, "");
}

class EdookitTimetableCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  static getStubConfig(hass) {
    const entity = Object.keys((hass && hass.states) || {}).find(
      (id) => id.startsWith("calendar.edookit_") && id.endsWith("_timetable"),
    );
    return { entity: entity || "" };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._payload = null;
    this._week = 0;
    this._lastToday = null;
    this._connected = false;
    this._unsubscribe = null;
    this._subscribing = false;
    this._retryTimer = null;
    this._generation = 0;
    this._connection = null;
    this._onReady = () => {
      this._teardown();
      this._ensureSubscribed();
    };
    this._language = null;
    this._overlay = null;
    this._overlayReturn = null;
    this._detailTimer = null;
    this._clockTimer = null;
    this._timed = [];

    const style = h("style");
    style.textContent = STYLE;
    this._card = h("ha-card");
    this._body = h("div", "card");
    this._card.append(this._body);
    this.shadowRoot.append(style, this._card);
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("The edookit-timetable-card needs an entity");
    }
    const style = config.style ?? DEFAULTS.style;
    if (!STYLES.includes(style)) {
      throw new Error(`style must be one of ${STYLES.join(", ")}`);
    }
    const entityChanged = this._config !== null && this._config.entity !== config.entity;
    this._config = { ...DEFAULTS, ...config, style };
    if (entityChanged) {
      this._payload = null;
      this._lastToday = null;
      this._closeDetail();
      this._teardown();
    }
    this._ensureSubscribed();
    this._render();
    this._scheduleClock();
  }

  set hass(hass) {
    this._hass = hass;
    this._watchConnection();
    const language = this._resolveLanguage();
    if (language !== this._language) this._render();
    this._ensureSubscribed();
  }

  getCardSize() {
    return 7;
  }

  connectedCallback() {
    this._connected = true;
    this._watchConnection();
    this._ensureSubscribed();
    this._scheduleClock();
  }

  disconnectedCallback() {
    this._connected = false;
    this._stopClock();
    this._closeDetail();
    this._unwatchConnection();
    this._teardown();
  }

  // The websocket library re-sends old subscriptions after a reconnect without
  // handling rejection, so a restarting HA (unknown_command, not_found) would
  // leave the card frozen. Subscribe with resubscribe: false and redo it on "ready".
  _watchConnection() {
    const connection = this._hass && this._hass.connection;
    if (!this._connected || connection === this._connection) return;
    const replaced = this._connection !== null;
    this._unwatchConnection();
    if (connection && typeof connection.addEventListener === "function") {
      connection.addEventListener("ready", this._onReady);
      this._connection = connection;
    }
    if (replaced) this._teardown();
  }

  _unwatchConnection() {
    if (this._connection) this._connection.removeEventListener("ready", this._onReady);
    this._connection = null;
  }

  _resolveLanguage() {
    const configured = this._config && this._config.language;
    if (configured === "cs" || configured === "en") return configured;
    return userLanguage(this._hass);
  }

  _ensureSubscribed() {
    if (this._unsubscribe || this._subscribing || this._retryTimer !== null) return;
    this._subscribe();
  }

  _subscribe() {
    if (!this._connected || !this._hass || !this._config) return;
    if (this._unsubscribe || this._subscribing) return;
    const generation = ++this._generation;
    this._subscribing = true;
    let pending;
    try {
      pending = this._hass.connection.subscribeMessage(
        (event) => this._onEvent(generation, event),
        { type: "edookit/week/subscribe", entity_id: this._config.entity },
        { resubscribe: false },
      );
    } catch (err) {
      pending = Promise.reject(err);
    }
    Promise.resolve(pending).then(
      (unsubscribe) => {
        if (generation !== this._generation) {
          this._safeCall(unsubscribe);
          return;
        }
        this._subscribing = false;
        this._unsubscribe = unsubscribe;
      },
      () => {
        if (generation !== this._generation) return;
        this._subscribing = false;
        this._scheduleRetry();
      },
    );
  }

  _onEvent(generation, event) {
    if (generation !== this._generation || !event) return;
    if (event.unloaded) {
      this._teardown();
      this._scheduleRetry();
      return;
    }
    if (!Array.isArray(event.weeks)) return;
    if (event.today !== this._lastToday) {
      this._lastToday = event.today;
      this._week = defaultWeek(event);
    }
    this._payload = event;
    this._render();
  }

  _scheduleRetry() {
    if (this._retryTimer !== null) clearTimeout(this._retryTimer);
    this._retryTimer = setTimeout(() => {
      this._retryTimer = null;
      this._subscribe();
    }, RETRY_MS);
    this._render();
  }

  _teardown() {
    this._generation++;
    if (this._retryTimer !== null) {
      clearTimeout(this._retryTimer);
      this._retryTimer = null;
    }
    const unsubscribe = this._unsubscribe;
    this._unsubscribe = null;
    this._subscribing = false;
    if (unsubscribe) this._safeCall(unsubscribe);
  }

  _safeCall(unsubscribe) {
    try {
      Promise.resolve(unsubscribe()).catch(() => {});
    } catch (err) {
      // The server forgets the subscription on its own when it unloads.
    }
  }

  // Glow marks the lesson in progress, so it re-checks the clock at the start
  // of every minute instead of waiting for the next timetable push.
  _scheduleClock() {
    this._stopClock();
    if (!this._connected || !this._config || this._config.style !== "glow") return;
    this._clockTimer = setTimeout(() => {
      this._markNow();
      this._scheduleClock();
    }, MINUTE_MS - (Date.now() % MINUTE_MS) + 50);
  }

  _stopClock() {
    clearTimeout(this._clockTimer);
    this._clockTimer = null;
  }

  _markNow() {
    if (this._config.style !== "glow" || !this._payload) return;
    const time = this._clock();
    this._timed.forEach((entry) => {
      const running = entry.start === null || (entry.start <= time && time < entry.end);
      entry.tile.className =
        entry.date === this._payload.today && running ? `${entry.base} now` : entry.base;
    });
  }

  _clock() {
    return PRAGUE_CLOCK.format(new Date());
  }

  _render() {
    this._language = this._resolveLanguage();
    const t = STRINGS[this._language];
    const style = this._config ? this._config.style : "classic";
    this._card.className = `style-${style}`;
    this._body.className = `card style-${style}`;
    this._timed = [];
    this._body.replaceChildren();

    const showHeader = !this._config || this._config.show_header !== false;
    const index = showHeader || !this._payload ? this._week : defaultWeek(this._payload);
    const week = this._payload && this._payload.weeks[index];
    if (!week) {
      const unavailable = this._retryTimer !== null;
      this._body.append(h("div", "status", unavailable ? t.unavailable : t.loading));
      return;
    }

    if (showHeader) this._body.append(this._renderHead(week, t));
    if (!week.loaded || week.periods.length === 0) {
      this._body.append(h("div", "status", t.notLoaded));
      return;
    }
    this._body.append(this._renderGrid(week, t));
    this._markNow();
    if (this._retryTimer !== null) this._body.append(h("div", "status", t.unavailable));
  }

  _renderHead(week, t) {
    const head = h("div", "head");
    head.append(h("div", "title", weekTitle(week.monday)));
    const switcher = h("div", "switch");
    [t.thisWeek, t.nextWeek].forEach((label, index) => {
      const button = h("button", "", label);
      button.type = "button";
      button.setAttribute("aria-pressed", String(this._week === index));
      button.addEventListener("click", () => {
        this._week = index;
        this._render();
      });
      switcher.append(button);
    });
    head.append(switcher);
    return head;
  }

  // Every tile is placed with explicit grid-row/grid-column so that spanning
  // event tiles can be added to a day row without touching the lessons.
  _renderGrid(week, t) {
    const grid = h("div", "grid");
    const showPeriods = this._config.show_periods !== false;
    const showDays = this._config.show_days !== false;
    const events = week.days.flatMap((day) => day.events);
    const hasBefore = events.some((event) => event.edge === "before");
    const hasAfter = events.some((event) => event.edge === "after");
    const tracks = showDays ? ["auto"] : [];
    const beforeColumn = tracks.length + 1;
    if (hasBefore) tracks.push(EDGE_TRACK);
    const firstColumn = tracks.length + 1;
    tracks.push(`repeat(${week.periods.length}, minmax(0, 1fr))`);
    if (hasAfter) tracks.push(EDGE_TRACK);
    grid.style.gridTemplateColumns = tracks.join(" ");
    const columnOf = new Map(week.periods.map((p, index) => [p.number, index + firstColumn]));
    const afterColumn = week.periods.length + firstColumn;

    const rows = showPeriods ? ["auto"] : [];
    const firstRow = rows.length + 1;
    rows.push(`repeat(${week.days.length}, minmax(46px, auto))`);
    grid.style.gridTemplateRows = rows.join(" ");

    if (showPeriods) {
      week.periods.forEach((period) => {
        const head = h("div", "period-head");
        head.append(h("b", "", String(period.number)), document.createTextNode(clockLabel(period.start)));
        head.style.gridColumn = String(columnOf.get(period.number));
        grid.append(head);
      });
    }

    week.days.forEach((day, index) => {
      const row = index + firstRow;
      const isToday = day.date === this._payload.today;
      if (showDays) {
        const label = h("div", isToday ? "day today" : "day", t.days[index]);
        label.append(h("small", "", shortDate(day.date)));
        label.style.gridRow = String(row);
        label.style.gridColumn = "1";
        grid.append(label);
      } else if (isToday) {
        const band = h("div", "today-row");
        band.style.gridRow = String(row);
        grid.append(band);
      }

      const place = (column, tiles) => {
        const cell = h("div", "cell");
        cell.style.gridRow = String(row);
        cell.style.gridColumn = column;
        tiles.forEach((tile) => cell.append(tile));
        grid.append(cell);
      };
      const eventTile = (event, edge) => this._renderEvent(event, day.date, index, t, edge);

      const byColumn = new Map();
      day.lessons.forEach((lesson) => {
        if (lesson.replaced_by) return;
        const column = columnOf.get(lesson.period);
        if (column === undefined) return;
        if (!byColumn.has(column)) byColumn.set(column, []);
        byColumn.get(column).push(lesson);
      });
      byColumn.forEach((lessons, column) => {
        place(
          String(column),
          lessons.map((lesson) => this._renderLesson(lesson, day.date, index, t)),
        );
      });

      const allDay = day.events.filter((event) => event.all_day);
      if (allDay.length) place(`${beforeColumn} / -1`, allDay.map((event) => eventTile(event, false)));

      const timed = day.events.filter((event) => !event.all_day);
      const before = timed.filter((event) => event.edge === "before");
      const after = timed.filter((event) => event.edge === "after");
      if (before.length) place(String(beforeColumn), before.map((event) => eventTile(event, true)));
      if (after.length) place(String(afterColumn), after.map((event) => eventTile(event, true)));

      const spans = timed
        .filter((event) => !event.edge && columnOf.has(event.first_period))
        .map((event) => ({
          event,
          start: columnOf.get(event.first_period),
          end: (columnOf.get(event.last_period) ?? columnOf.get(event.first_period)) + 1,
        }))
        .sort((a, b) => a.start - b.start || a.end - b.end);
      const clusters = [];
      spans.forEach((span) => {
        const last = clusters[clusters.length - 1];
        if (last && span.start < last.end) {
          last.end = Math.max(last.end, span.end);
          last.members.push(span.event);
        } else {
          clusters.push({ start: span.start, end: span.end, members: [span.event] });
        }
      });
      clusters.forEach((cluster) => {
        place(
          `${cluster.start} / ${cluster.end}`,
          cluster.members.map((event) => eventTile(event, false)),
        );
      });
    });
    return grid;
  }

  _renderLesson(lesson, date, dayIndex, t) {
    const classes = ["lesson"];
    const text = lesson.code || lesson.subject || "";
    if (!lesson.code && text.length > 6) classes.push(text.length > 14 ? "longer" : "long");
    if (lesson.changed) classes.push("changed");
    if (lesson.cancelled) classes.push("cancelled");
    const showRoom = this._config.show_room !== false;
    if (!showRoom) classes.push("noroom");

    const tile = h("button", classes.join(" "));
    tile.type = "button";
    if (!lesson.cancelled) {
      this._timed.push({ tile, base: tile.className, date, start: lesson.start, end: lesson.end });
    }
    tile.append(h("div", "code", text));
    if (showRoom && lesson.room) tile.append(h("div", "room", lesson.room));
    const times = `${clockLabel(lesson.start)}–${clockLabel(lesson.end)}`;
    tile.title = [lesson.subject, times, lesson.teacher].filter(Boolean).join(" · ");
    tile.addEventListener("click", () =>
      this._openDetail({
        title: lesson.subject || lesson.code || "",
        when: `${this._dayLabel(t, dayIndex, date)}, ${times}`,
        rows: [
          [t.teacher, [lesson.teacher]],
          [t.room, [lesson.room]],
          [t.topic, [lesson.note]],
        ],
        t,
      }),
    );
    return tile;
  }

  _renderEvent(event, date, dayIndex, t, edge) {
    const classes = ["event"];
    if (event.all_day) classes.push("allday");
    if (edge) classes.push("edge");
    const tile = h("button", classes.join(" "));
    tile.type = "button";
    this._timed.push({ tile, base: tile.className, date, start: event.start, end: event.end });
    tile.append(h("div", "etitle", event.title));
    const times = event.all_day ? null : `${clockLabel(event.start)}–${clockLabel(event.end)}`;
    const sub = h("div", "esub", event.all_day ? `${t.wholeDay} · ${t.noLessons}` : times);
    if (!event.all_day) sub.append(h("span", "hint", ` · ${t.tapDetails}`));
    tile.append(sub);
    tile.title = [event.title, times].filter(Boolean).join(" · ");
    tile.addEventListener("click", () =>
      this._openDetail({
        title: event.title,
        when: `${this._dayLabel(t, dayIndex, date)}, ${times || t.wholeDay}`,
        rows: [
          [t.insteadOf, (event.replaces || []).map((r) => `${r.period}. ${r.subject || ""}`.trim())],
          [t.description, [event.description]],
          [t.createdBy, [event.created_by]],
        ],
        t,
      }),
    );
    return tile;
  }

  _dayLabel(t, dayIndex, iso) {
    const { month, day } = isoParts(iso);
    return `${t.days[dayIndex]} ${t.date(day, month)}`;
  }

  _openDetail({ title, when, rows, t }) {
    this._closeDetail(false);
    const overlay = h("div", "overlay");
    const panel = h("div", "panel");
    panel.tabIndex = -1;
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    panel.setAttribute("aria-label", title);
    panel.append(h("h4", "", title), h("div", "when", when));
    rows.forEach(([label, values]) => {
      const shown = values.filter((value) => typeof value === "string" && value.trim());
      if (!shown.length) return;
      const row = h("div", "row");
      row.append(h("div", "label", label));
      const cell = h("div", "value");
      shown.forEach((value) => cell.append(h("div", "", value)));
      row.append(cell);
      panel.append(row);
    });
    const close = h("button", "close", t.close);
    close.type = "button";
    close.addEventListener("click", () => this._closeDetail());
    panel.append(close);
    overlay.append(panel);
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) this._closeDetail();
    });
    overlay.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        this._closeDetail();
      } else if (e.key === "Tab") {
        e.preventDefault();
        close.focus();
      }
    });
    this._overlayReturn = this.shadowRoot.activeElement;
    this._overlay = overlay;
    this.shadowRoot.append(overlay);
    panel.focus();
    this._detailTimer = setTimeout(() => this._closeDetail(), DETAIL_TIMEOUT_MS);
  }

  _closeDetail(restoreFocus = true) {
    if (this._detailTimer !== null) {
      clearTimeout(this._detailTimer);
      this._detailTimer = null;
    }
    if (!this._overlay) return;
    this._overlay.remove();
    this._overlay = null;
    const target = this._overlayReturn;
    this._overlayReturn = null;
    if (restoreFocus && target && target.isConnected) target.focus();
  }
}

const EDITOR_STRINGS = {
  cs: {
    labels: {
      entity: "Rozvrh",
      style: "Vzhled",
      language: "Jazyk",
      show_header: "Záhlaví s datem a přepínačem týdnů",
      show_periods: "Čísla a začátky hodin",
      show_days: "Dny v týdnu",
      show_room: "Učebna na dlaždici",
    },
    helpers: {
      style: "Záře je pro tmavé dashboardy bez rámečků karet.",
      language: "Bez výběru se řídí jazykem Home Assistantu.",
    },
    styles: { classic: "Klasický", glow: "Záře" },
  },
  en: {
    labels: {
      entity: "Timetable",
      style: "Style",
      language: "Language",
      show_header: "Header with date and week switch",
      show_periods: "Period numbers and start times",
      show_days: "Weekdays",
      show_room: "Room on the tiles",
    },
    helpers: {
      style: "Glow is for dark dashboards without card boxes.",
      language: "Leave empty to follow the Home Assistant language.",
    },
    styles: { classic: "Classic", glow: "Glow" },
  },
};

function editorSchema(t, entities) {
  const select = (options) => ({ select: { mode: "dropdown", options } });
  return [
    { name: "entity", required: true, selector: { entity: { include_entities: entities } } },
    {
      type: "grid",
      name: "",
      schema: [
        { name: "style", selector: select(STYLES.map((value) => ({ value, label: t.styles[value] }))) },
        {
          name: "language",
          selector: select([
            { value: "cs", label: "Čeština" },
            { value: "en", label: "English" },
          ]),
        },
      ],
    },
    {
      type: "grid",
      name: "",
      schema: ["show_header", "show_periods", "show_days", "show_room"].map((name) => ({
        name,
        selector: { boolean: {} },
      })),
    },
  ];
}

// ha-form reads each value straight from the config, so an option left out
// (meaning its default) would show as off. The form gets the defaults filled in
// and they are dropped again on the way out, so the YAML keeps only changes.
class EdookitTimetableCardEditor extends HTMLElement {
  constructor() {
    super();
    this._config = {};
    this._hass = null;
    this._form = null;
  }

  setConfig(config) {
    this._config = config;
    this._build();
  }

  // hass changes with every state in the system; the form is rebuilt only when
  // the entity registry or the user's language changes.
  set hass(hass) {
    const previous = this._hass;
    this._hass = hass;
    if (this._form) this._form.hass = hass;
    if (
      !previous ||
      previous.entities !== hass.entities ||
      userLanguage(previous) !== userLanguage(hass)
    ) {
      this._build();
    }
  }

  _build() {
    if (!this._hass) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (e) => this._changed(e.detail.value));
      this.append(this._form);
    }
    const t = EDITOR_STRINGS[userLanguage(this._hass)];
    const entities = Object.values(this._hass.entities || {})
      .filter((entry) => entry.platform === "edookit" && entry.translation_key === "timetable")
      .map((entry) => entry.entity_id);
    if (this._config.entity && !entities.includes(this._config.entity)) {
      entities.push(this._config.entity);
    }
    this._form.hass = this._hass;
    this._form.schema = editorSchema(t, entities);
    this._form.computeLabel = (field) => t.labels[field.name];
    this._form.computeHelper = (field) => t.helpers[field.name];
    this._form.data = { ...DEFAULTS, ...this._config };
  }

  _changed(value) {
    const config = { ...this._config, ...value };
    Object.keys(config).forEach((key) => {
      if ([undefined, null, "", DEFAULTS[key]].includes(config[key])) delete config[key];
    });
    this.dispatchEvent(
      new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }),
    );
  }
}

// Extra modules run before the frontend boots. Its app bundle then swaps in a
// scoped-registry polyfill that has never heard of elements defined earlier, so
// the dashboard reports "Custom element doesn't exist". Waiting for the
// frontend's own root element means we define through the polyfill.
customElements.whenDefined("home-assistant").then(() => {
  if (!customElements.get(CARD_TAG)) {
    customElements.define(CARD_TAG, EdookitTimetableCard);
  }
  if (!customElements.get(EDITOR_TAG)) {
    customElements.define(EDITOR_TAG, EdookitTimetableCardEditor);
  }
});

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === CARD_TAG)) {
  window.customCards.push({
    type: CARD_TAG,
    name: "Edookit timetable",
    description: "Weekly timetable with substitutions and school events from Edookit",
  });
}
