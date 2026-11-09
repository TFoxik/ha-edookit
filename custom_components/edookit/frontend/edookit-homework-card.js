const CARD_TAG = "edookit-homework-card";
const EDITOR_TAG = "edookit-homework-card-editor";
const RETRY_MS = 30000;
const MINUTE_MS = 60000;
const DAY_MS = 86400000;
const VIEWS = ["list", "compact"];
const DEFAULTS = {
  view: "list",
  max_items: 5,
  keep_overdue_days: 2,
  show_header: true,
  show_teacher: true,
  group_by_due: true,
  show_countdown: true,
};
const GROUPS = ["overdue", "today", "tomorrow", "week", "later", "none"];
const NO_COURSE = "📚";
const PRAGUE = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/Prague",
  year: "numeric",
  month: "numeric",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const STRINGS = {
  cs: {
    title: "Domácí úkoly",
    groups: {
      overdue: "Po termínu",
      today: "Dnes",
      tomorrow: "Zítra",
      week: "Tento týden",
      later: "Později",
      none: "Bez termínu",
    },
    countdown: {
      today: "dnes",
      tomorrow: "zítra",
      days: (n) => `za ${n} ${n <= 4 ? "dny" : "dní"}`,
      overdue: "po termínu",
    },
    weekdays: ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"],
    deadline: (weekday, day, month, time) => `${weekday} ${day}. ${month}. ${time}`,
    empty: "Žádné úkoly",
    unavailable: "Úkoly nejsou dostupné",
    loading: "Načítám…",
    showMore: (n) => `Zobrazit dalších ${n} úkolů`,
    showLess: "Zobrazit méně úkolů",
    count: (n) => `${n} ${n === 1 ? "úkol" : n <= 4 ? "úkoly" : "úkolů"}`,
    overdueCount: (n) => ` · ${n} po termínu`,
    nearest: (short, deadline) => `Nejbližší: ${short} · ${deadline}`,
    close: "Zavřít",
  },
  en: {
    title: "Homework",
    groups: {
      overdue: "Overdue",
      today: "Today",
      tomorrow: "Tomorrow",
      week: "This week",
      later: "Later",
      none: "No deadline",
    },
    countdown: {
      today: "today",
      tomorrow: "tomorrow",
      days: (n) => `in ${n} days`,
      overdue: "overdue",
    },
    weekdays: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    deadline: (weekday, day, month, time) => `${weekday} ${day} ${MONTHS[month - 1]} ${time}`,
    empty: "No homework",
    unavailable: "Homework unavailable",
    loading: "Loading…",
    showMore: (n) => `Show ${n} more`,
    showLess: "Show fewer",
    count: (n) => `${n} ${n === 1 ? "assignment" : "assignments"}`,
    overdueCount: (n) => ` · ${n} overdue`,
    nearest: (short, deadline) => `Next: ${short} · ${deadline}`,
    close: "Close",
  },
};

const STYLE = `
  :host { display: block; --overdue: var(--edookit-overdue-color, #e53935);
    --soon: var(--edookit-soon-color, #e65100);
    --t-title: var(--edookit-font-title, 16px); --t-text: var(--edookit-font-text, 14px);
    --t-meta: var(--edookit-font-meta, 12px); --t-min: var(--edookit-font-min, 11px); }
  ha-card { display: block; padding: 12px; font-size: var(--t-text); }
  .card { color: var(--primary-text-color); }
  .head { display: flex; justify-content: space-between; align-items: center; gap: 8px;
    margin-bottom: 4px; }
  .title { font-size: var(--t-title); font-weight: 600; }
  .more { display: flex; align-items: center; gap: 6px; cursor: pointer; outline: none;
    border-radius: 6px; }
  .more:focus-visible { box-shadow: 0 0 0 2px var(--primary-color); }
  .more.below { justify-content: center; padding: 6px 0 0; }
  .count { font-size: var(--t-min); line-height: 1.5; padding: 0 7px; border-radius: 999px;
    color: var(--secondary-text-color);
    background: color-mix(in srgb, var(--secondary-text-color) 14%, transparent); }
  .status { font-size: var(--t-meta); color: var(--secondary-text-color); padding: 4px 0; }
  .group { font-size: var(--t-meta); font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.04em; color: var(--secondary-text-color); padding: 8px 0 2px; }
  .row { display: flex; gap: 10px; align-items: center; padding: 6px 0;
    border-top: 1px solid var(--divider-color); }
  .group + .row { border-top: none; }
  .short { flex: none; min-width: 2.4em; padding: 2px 6px; box-sizing: border-box;
    border-radius: 6px; text-align: center; font-size: var(--t-meta); font-weight: 700;
    background: var(--secondary-background-color); }
  .main { min-width: 0; flex: 1; }
  .text { overflow-wrap: anywhere; }
  .meta { font-size: var(--t-meta); color: var(--secondary-text-color); overflow-wrap: anywhere; }
  .due { flex: none; text-align: right; font-size: var(--t-meta);
    color: var(--secondary-text-color); }
  .countdown { display: block; font-weight: 600; }
  .row.overdue .due, .row.overdue .short { color: var(--overdue); }
  .row.soon .due, .row.soon .short { color: var(--soon); }
  .tile { padding: 10px 12px; border-radius: 10px; cursor: pointer; outline: none;
    background: var(--secondary-background-color); }
  .tile:focus-visible { box-shadow: 0 0 0 2px var(--primary-color); }
  .total { font-size: var(--t-title); font-weight: 600; }
  .nearest { font-size: var(--t-meta); color: var(--secondary-text-color); }
  .nearest.overdue { color: var(--overdue); }
  .overlay { position: fixed; inset: 0; z-index: 10; box-sizing: border-box; padding: 16px;
    display: flex; align-items: center; justify-content: center; background: rgba(0, 0, 0, 0.45); }
  .panel { box-sizing: border-box; width: 100%; max-width: 560px; max-height: 100%;
    overflow: auto; padding: 14px 16px; border-radius: 12px; outline: none;
    border: 1px solid var(--divider-color);
    background: var(--card-background-color, #fff); color: var(--primary-text-color);
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25); font-size: var(--t-text); }
  .panel h4 { margin: 0 0 2px; font-size: var(--t-title); line-height: 1.25; }
  .panel .close { font: inherit; margin-top: 8px; padding: 0 16px; min-height: 36px;
    border-radius: 999px; cursor: pointer; border: 1px solid var(--primary-color);
    background: var(--primary-color); color: var(--text-primary-color, #fff); }
`;

const FONT_SIZES = ["title", "text", "meta", "min"];

function checkFontSizes(sizes) {
  if (sizes === undefined) return;
  if (sizes === null || typeof sizes !== "object" || Array.isArray(sizes)) {
    throw new Error(`font_sizes must be a map with ${FONT_SIZES.join(", ")}`);
  }
  for (const [key, value] of Object.entries(sizes)) {
    if (!FONT_SIZES.includes(key)) {
      throw new Error(`font_sizes takes only ${FONT_SIZES.join(", ")}`);
    }
    if (!(typeof value === "number" && value >= 8 && value <= 48)) {
      throw new Error(`font_sizes.${key} must be a number of pixels from 8 to 48`);
    }
  }
}

// An inline style on the host beats the :host defaults and any theme value.
function applyFontSizes(host, sizes) {
  for (const key of FONT_SIZES) {
    if (sizes && sizes[key] !== undefined) host.style.setProperty(`--t-${key}`, `${sizes[key]}px`);
    else host.style.removeProperty(`--t-${key}`);
  }
}

function h(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined && text !== null) el.textContent = text;
  return el;
}

function activatable(el, onActivate) {
  el.setAttribute("role", "button");
  el.tabIndex = 0;
  el.addEventListener("click", onActivate);
  el.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onActivate();
    }
  });
  return el;
}

function userLanguage(hass) {
  const locale = hass && hass.locale && hass.locale.language;
  return typeof locale === "string" && locale.startsWith("cs") ? "cs" : "en";
}

function pragueParts(ms) {
  const parts = {};
  PRAGUE.formatToParts(ms).forEach(({ type, value }) => {
    parts[type] = Number(value);
  });
  return parts;
}

function pragueDay(ms) {
  const { year, month, day } = pragueParts(ms);
  return Date.UTC(year, month - 1, day) / DAY_MS;
}

// 1970-01-01 was a Thursday; Monday is 0.
function weekdayIndex(dayNumber) {
  return (dayNumber + 3) % 7;
}

function deadlineLabel(t, ms) {
  const { month, day, hour, minute } = pragueParts(ms);
  const time = `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
  return t.deadline(t.weekdays[weekdayIndex(pragueDay(ms))], day, month, time);
}

function parseDue(iso) {
  const ms = iso ? Date.parse(iso) : NaN;
  return Number.isNaN(ms) ? null : ms;
}

function groupOf(overdue, days, today) {
  if (days === null) return "none";
  if (overdue) return "overdue";
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  return days <= 6 - weekdayIndex(today) ? "week" : "later";
}

function countdownLabel(t, { days, overdue }) {
  if (days === null) return "";
  if (overdue) return t.countdown.overdue;
  if (days === 0) return t.countdown.today;
  return days === 1 ? t.countdown.tomorrow : t.countdown.days(days);
}

class EdookitHomeworkCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  static getStubConfig(hass) {
    const entity = Object.keys((hass && hass.states) || {}).find(
      (id) => id.startsWith("sensor.edookit_") && id.endsWith("_homework"),
    );
    return { entity: entity || "" };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._payload = null;
    this._connected = false;
    this._unsubscribe = null;
    this._subscribing = false;
    this._retryTimer = null;
    this._tickTimer = null;
    this._shown = "";
    this._generation = 0;
    this._connection = null;
    this._onReady = () => {
      this._teardown();
      this._ensureSubscribed();
    };
    this._language = null;
    this._expanded = false;
    this._overlay = null;
    this._overlayBody = null;
    this._tile = null;
    this._clock = () => Date.now();

    const style = h("style");
    style.textContent = STYLE;
    this._card = h("ha-card");
    this._body = h("div", "card");
    this._card.append(this._body);
    this.shadowRoot.append(style, this._card);
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("The edookit-homework-card needs an entity");
    }
    checkFontSizes(config.font_sizes);
    if (config.view !== undefined && !VIEWS.includes(config.view)) {
      throw new Error(`view must be one of ${VIEWS.join(", ")}`);
    }
    const max = config.max_items;
    if (max !== undefined && !(Number.isInteger(max) && max > 0)) {
      throw new Error("max_items must be a positive whole number");
    }
    const keep = config.keep_overdue_days;
    if (keep !== undefined && !(Number.isInteger(keep) && keep >= 0)) {
      throw new Error("keep_overdue_days must be a whole number, 0 or more");
    }
    const entityChanged = this._config !== null && this._config.entity !== config.entity;
    this._config = { ...DEFAULTS, ...config };
    applyFontSizes(this, config.font_sizes);
    this._closePopup(false);
    if (entityChanged) {
      this._payload = null;
      this._expanded = false;
      this._teardown();
    }
    this._ensureSubscribed();
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._watchConnection();
    if (this._resolveLanguage() !== this._language) this._render();
    this._ensureSubscribed();
  }

  getCardSize() {
    return 4;
  }

  connectedCallback() {
    this._connected = true;
    this._watchConnection();
    this._ensureSubscribed();
    this._render();
  }

  disconnectedCallback() {
    this._connected = false;
    this._stopTick();
    this._closePopup(false);
    this._unwatchConnection();
    this._teardown();
  }

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
        { type: "edookit/homework/subscribe", entity_id: this._config.entity },
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
    if (!Array.isArray(event.homework)) return;
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

  // Items drop off at their deadline plus keep_overdue_days, so the card
  // re-checks the clock every minute instead of waiting for the 3-hour refresh.
  _startTick() {
    this._stopTick();
    if (!this._connected) return;
    this._tickTimer = setTimeout(() => {
      this._tickTimer = null;
      if (this._signature(this._entries(this._clock())) === this._shown) this._startTick();
      else this._render();
    }, MINUTE_MS);
  }

  _stopTick() {
    if (this._tickTimer !== null) clearTimeout(this._tickTimer);
    this._tickTimer = null;
  }

  _entries(now) {
    const payload = this._payload;
    if (!payload || !payload.available) return null;
    const keep = this._config.keep_overdue_days * DAY_MS;
    const today = pragueDay(now);
    const entries = [];
    payload.homework.forEach((item) => {
      if (item.done) return;
      const due = parseDue(item.due);
      if (due !== null && now >= due + keep) return;
      const overdue = due !== null && now >= due;
      const days = due === null ? null : pragueDay(due) - today;
      entries.push({ item, due, overdue, days, group: groupOf(overdue, days, today) });
    });
    return entries.sort(
      (a, b) =>
        (a.due === null) - (b.due === null) || (a.due || 0) - (b.due || 0) || a.item.id - b.item.id,
    );
  }

  _signature(entries) {
    if (!entries) return "";
    return entries
      .map(({ item, group, overdue, days }) => `${item.id}:${group}:${overdue}:${days}`)
      .join(",");
  }

  _fillContent(into, t, entries, loading, fill) {
    if (entries === null) into.append(h("div", "status", loading ? t.loading : t.unavailable));
    else if (!entries.length) into.append(h("div", "status", t.empty));
    else fill(entries);
  }

  _render() {
    if (!this._config) return;
    this._startTick();
    this._language = this._resolveLanguage();
    const t = STRINGS[this._language];
    const entries = this._entries(this._clock());
    this._shown = this._signature(entries);
    if (this._overlayBody) this._fillPopup(t, entries);
    this._body.replaceChildren();
    const head = h("div", "head");
    const showHeader = this._config.show_header !== false;
    if (showHeader) {
      head.append(h("span", "title", t.title));
      this._body.append(head);
    }
    const loading = !this._payload && this._retryTimer === null;
    this._fillContent(this._body, t, entries, loading, (list) => {
      if (this._config.view === "compact") {
        this._body.append(this._compactTile(t, list));
        return;
      }
      const shown = this._expanded ? list : list.slice(0, this._config.max_items);
      const hidden = list.length - shown.length;
      const toggle = list.length > this._config.max_items;
      if (toggle && showHeader) head.append(this._toggle(t, hidden, false));
      this._renderRows(t, this._body, shown);
      if (toggle && !showHeader) this._body.append(this._toggle(t, hidden, true));
    });
  }

  _compactTile(t, entries) {
    const overdue = entries.filter((entry) => entry.overdue);
    const total = t.count(entries.length) + (overdue.length ? t.overdueCount(overdue.length) : "");
    const tile = activatable(h("div", "tile"), () => this._openPopup());
    tile.setAttribute("aria-haspopup", "dialog");
    this._tile = tile;
    tile.append(h("div", "total", total));
    const ahead = entries.find((entry) => entry.due !== null && !entry.overdue);
    const next = ahead || overdue[0];
    if (next) {
      const label = t.nearest(next.item.short || NO_COURSE, deadlineLabel(t, next.due));
      const late = !ahead;
      tile.append(
        h("div", late ? "nearest overdue" : "nearest", late ? `${label} · ${t.countdown.overdue}` : label),
      );
    }
    return tile;
  }

  _fillPopup(t, entries) {
    this._overlayBody.replaceChildren();
    this._fillContent(this._overlayBody, t, entries, false, (list) =>
      this._renderRows(t, this._overlayBody, list),
    );
  }

  _openPopup() {
    if (this._overlay) return;
    const t = STRINGS[this._resolveLanguage()];
    const overlay = h("div", "overlay");
    const panel = h("div", "panel");
    panel.tabIndex = -1;
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    panel.setAttribute("aria-label", t.title);
    const body = h("div");
    const close = h("button", "close", t.close);
    close.type = "button";
    close.addEventListener("click", () => this._closePopup());
    panel.append(h("h4", "", t.title), body, close);
    overlay.append(panel);
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) this._closePopup();
    });
    overlay.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        this._closePopup();
      } else if (e.key === "Tab") {
        e.preventDefault();
        close.focus();
      }
    });
    this._overlay = overlay;
    this._overlayBody = body;
    this._fillPopup(t, this._entries(this._clock()));
    this.shadowRoot.append(overlay);
    panel.focus();
  }

  _closePopup(restoreFocus = true) {
    if (!this._overlay) return;
    this._overlay.remove();
    this._overlay = null;
    this._overlayBody = null;
    if (restoreFocus && this._tile) this._tile.focus();
  }

  _toggle(t, hidden, below) {
    const el = activatable(h("div", below ? "more below" : "more"), () => {
      this._expanded = !this._expanded;
      this._render();
    });
    el.setAttribute("aria-expanded", String(this._expanded));
    el.setAttribute("aria-label", this._expanded ? t.showLess : t.showMore(hidden));
    el.append(h("span", "count", this._expanded ? "−" : `+${hidden}`));
    return el;
  }

  _renderRows(t, into, entries) {
    if (!this._config.group_by_due) {
      entries.forEach((entry) => into.append(this._row(t, entry)));
      return;
    }
    const buckets = new Map(GROUPS.map((group) => [group, []]));
    entries.forEach((entry) => buckets.get(entry.group).push(entry));
    GROUPS.forEach((group) => {
      const members = buckets.get(group);
      if (!members.length) return;
      into.append(h("div", "group", t.groups[group]));
      members.forEach((entry) => into.append(this._row(t, entry)));
    });
  }

  _row(t, entry) {
    const { item, due, overdue, days } = entry;
    const soon = !overdue && days !== null && days <= 1;
    const row = h("div", overdue ? "row overdue" : soon ? "row soon" : "row");
    row.setAttribute("data-id", String(item.id));
    const main = h("div", "main");
    main.append(h("div", "text", item.text || item.title));
    const meta = [item.subject, this._config.show_teacher ? item.teacher : null];
    const line = meta.filter(Boolean).join(" · ");
    if (line) main.append(h("div", "meta", line));
    row.append(h("span", "short", item.short || NO_COURSE), main);
    if (due !== null) {
      const when = h("div", "due");
      when.append(h("span", "deadline", deadlineLabel(t, due)));
      if (this._config.show_countdown) when.append(h("span", "countdown", countdownLabel(t, entry)));
      row.append(when);
    }
    return row;
  }
}

const EDITOR_STRINGS = {
  cs: {
    labels: {
      entity: "Domácí úkoly",
      view: "Zobrazení",
      max_items: "Počet úkolů",
      keep_overdue_days: "Dny po termínu",
      language: "Jazyk",
      show_header: "Záhlaví",
      show_teacher: "Učitel",
      group_by_due: "Seskupit podle termínu",
      show_countdown: "Odpočet",
    },
    helpers: {
      language: "Bez výběru se řídí jazykem Home Assistantu.",
    },
    views: { list: "Seznam", compact: "Kompaktní" },
  },
  en: {
    labels: {
      entity: "Homework",
      view: "View",
      max_items: "Items shown",
      keep_overdue_days: "Days kept after deadline",
      language: "Language",
      show_header: "Header",
      show_teacher: "Teacher",
      group_by_due: "Group by deadline",
      show_countdown: "Countdown",
    },
    helpers: {
      language: "Leave empty to follow the Home Assistant language.",
    },
    views: { list: "List", compact: "Compact" },
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
        {
          name: "view",
          selector: select(VIEWS.map((value) => ({ value, label: t.views[value] }))),
        },
        { name: "max_items", selector: { number: { min: 1, mode: "box" } } },
        { name: "keep_overdue_days", selector: { number: { min: 0, mode: "box" } } },
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
      schema: ["show_header", "show_teacher", "group_by_due", "show_countdown"].map((name) => ({
        name,
        selector: { boolean: {} },
      })),
    },
  ];
}

// Same scheme as the other editors: defaults filled in for ha-form, which
// would show a left-out option as empty, and dropped again on the way out.
class EdookitHomeworkCardEditor extends HTMLElement {
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
      .filter((entry) => entry.platform === "edookit" && entry.translation_key === "homework")
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

// Defined once the frontend's root element exists, for the same scoped-registry
// reason as the timetable card.
customElements.whenDefined("home-assistant").then(() => {
  if (!customElements.get(CARD_TAG)) {
    customElements.define(CARD_TAG, EdookitHomeworkCard);
  }
  if (!customElements.get(EDITOR_TAG)) {
    customElements.define(EDITOR_TAG, EdookitHomeworkCardEditor);
  }
});

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === CARD_TAG)) {
  window.customCards.push({
    type: CARD_TAG,
    name: "Edookit homework",
    description: "Open homework from Edookit, grouped by deadline",
  });
}
