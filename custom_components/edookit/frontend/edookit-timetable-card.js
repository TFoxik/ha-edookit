const CARD_TAG = "edookit-timetable-card";
const RETRY_MS = 30000;

const STRINGS = {
  cs: {
    thisWeek: "Tento týden",
    nextWeek: "Příští týden",
    notLoaded: "Rozvrh zatím není načten",
    projected:
      "Rozvrh příštího týdne je odhad podle tohoto; suplování se objeví, až týden začne",
    loading: "Načítám…",
    unavailable: "Rozvrh není dostupný, zkouším znovu",
    days: ["Po", "Út", "St", "Čt", "Pá"],
  },
  en: {
    thisWeek: "This week",
    nextWeek: "Next week",
    notLoaded: "Timetable not loaded yet",
    projected:
      "Next week's lessons are copied from this week; substitutions appear once that week starts.",
    loading: "Loading…",
    unavailable: "Timetable unavailable, retrying",
    days: ["Mon", "Tue", "Wed", "Thu", "Fri"],
  },
};

const STYLE = `
  :host { display: block; }
  ha-card { display: block; padding: 12px; }
  .card { container-type: inline-size; color: var(--primary-text-color); }
  .head { display: flex; justify-content: space-between; align-items: center; gap: 8px;
    flex-wrap: wrap; margin-bottom: 8px; }
  .title { font-size: 18px; font-weight: 600; }
  .switch { display: flex; gap: 6px; }
  .switch button { font: inherit; font-size: 12px; padding: 3px 10px; border-radius: 999px;
    border: 1px solid var(--divider-color); background: none; color: var(--secondary-text-color);
    cursor: pointer; }
  .switch button[aria-pressed="true"] { background: var(--primary-color);
    border-color: var(--primary-color); color: var(--text-primary-color, #fff); }
  .grid { display: grid; gap: 4px; grid-auto-rows: minmax(46px, auto); }
  .period-head { grid-row: 1; align-self: end; font-size: 10px; line-height: 1.2; text-align: center;
    color: var(--secondary-text-color); }
  .period-head b { display: block; font-size: 12px; color: var(--primary-text-color); }
  .day { font-size: 14px; font-weight: 600; line-height: 1.1; padding-top: 6px; }
  .day small { display: block; font-weight: 400; font-size: 10px;
    color: var(--secondary-text-color); }
  .day.today, .day.today small { color: var(--primary-color); }
  .cell { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .lesson { flex: 1; display: flex; flex-direction: column; justify-content: center;
    min-width: 0; min-height: 40px; box-sizing: border-box; padding: 4px 2px; text-align: center;
    border: 1px solid var(--divider-color); border-radius: 8px;
    background: var(--secondary-background-color); }
  .lesson .code { font-size: 20px; font-weight: 500; line-height: 1.15; overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap; }
  .lesson .room { font-size: 10px; color: var(--secondary-text-color); overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap; }
  .lesson.long .code { font-size: 11px; white-space: normal; overflow-wrap: anywhere;
    hyphens: auto; }
  .lesson.longer .code { font-size: 9px; }
  .lesson.changed { border-color: var(--primary-color); }
  .lesson.cancelled { opacity: 0.55; }
  .lesson.cancelled .code { text-decoration: line-through; }
  .note, .status { font-size: 12px; color: var(--secondary-text-color); margin-top: 8px; }
  .status { margin-top: 4px; }
  @container (max-width: 480px) {
    .title { font-size: 15px; }
    .day { font-size: 12px; }
    .day small { font-size: 9px; }
    .lesson { min-height: 36px; }
    .lesson .code { font-size: 15px; }
    .lesson .room { font-size: 9px; }
    .lesson.long .code { font-size: 9px; }
    .lesson.longer .code { font-size: 8px; }
  }
`;

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

function clockLabel(hhmm) {
  return hhmm.replace(/^0/, "");
}

class EdookitTimetableCard extends HTMLElement {
  static getStubConfig() {
    return { entity: "" };
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
    const entityChanged = this._config !== null && this._config.entity !== config.entity;
    this._config = { ...config };
    if (entityChanged) {
      this._payload = null;
      this._lastToday = null;
      this._teardown();
    }
    this._ensureSubscribed();
    this._render();
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
  }

  disconnectedCallback() {
    this._connected = false;
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
    const locale = this._hass && this._hass.locale && this._hass.locale.language;
    return typeof locale === "string" && locale.startsWith("cs") ? "cs" : "en";
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
      this._week = event.default_week === 1 ? 1 : 0;
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

  _render() {
    this._language = this._resolveLanguage();
    const t = STRINGS[this._language];
    this._body.replaceChildren();

    const week = this._payload && this._payload.weeks[this._week];
    if (!week) {
      const unavailable = this._retryTimer !== null;
      this._body.append(h("div", "status", unavailable ? t.unavailable : t.loading));
      return;
    }

    this._body.append(this._renderHead(week, t));
    if (!week.loaded) {
      this._body.append(h("div", "status", t.notLoaded));
      return;
    }
    this._body.append(this._renderGrid(week, t));
    if (week.projected) this._body.append(h("div", "note", t.projected));
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
    const columnOf = new Map(week.periods.map((p, index) => [p.number, index + 2]));
    grid.style.gridTemplateColumns = `auto repeat(${week.periods.length}, minmax(0, 1fr))`;

    week.periods.forEach((period) => {
      const head = h("div", "period-head");
      head.append(h("b", "", String(period.number)), document.createTextNode(clockLabel(period.start)));
      head.style.gridColumn = String(columnOf.get(period.number));
      grid.append(head);
    });

    week.days.forEach((day, index) => {
      const row = index + 2;
      const label = h("div", day.date === this._payload.today ? "day today" : "day", t.days[index]);
      label.append(h("small", "", shortDate(day.date)));
      label.style.gridRow = String(row);
      label.style.gridColumn = "1";
      grid.append(label);

      const byColumn = new Map();
      day.lessons.forEach((lesson) => {
        const column = columnOf.get(lesson.period);
        if (column === undefined) return;
        if (!byColumn.has(column)) byColumn.set(column, []);
        byColumn.get(column).push(lesson);
      });
      byColumn.forEach((lessons, column) => {
        const cell = h("div", "cell");
        cell.style.gridRow = String(row);
        cell.style.gridColumn = String(column);
        lessons.forEach((lesson) => cell.append(this._renderLesson(lesson)));
        grid.append(cell);
      });
    });
    return grid;
  }

  _renderLesson(lesson) {
    const classes = ["lesson"];
    const text = lesson.code || lesson.subject || "";
    if (!lesson.code && text.length > 6) classes.push(text.length > 14 ? "longer" : "long");
    if (lesson.changed) classes.push("changed");
    if (lesson.cancelled) classes.push("cancelled");

    const tile = h("div", classes.join(" "));
    tile.append(h("div", "code", text));
    if (lesson.room) tile.append(h("div", "room", lesson.room));
    const details = [lesson.subject, `${clockLabel(lesson.start)}–${clockLabel(lesson.end)}`, lesson.teacher];
    tile.title = details.filter(Boolean).join(" · ");
    return tile;
  }
}

if (!customElements.get(CARD_TAG)) {
  customElements.define(CARD_TAG, EdookitTimetableCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === CARD_TAG)) {
  window.customCards.push({
    type: CARD_TAG,
    name: "Edookit timetable",
    description: "Weekly timetable with substitutions and school events from Edookit",
  });
}
