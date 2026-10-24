const CARD_TAG = "edookit-grades-card";
const EDITOR_TAG = "edookit-grades-card-editor";
const RETRY_MS = 30000;
const VIEWS = ["latest", "subjects", "combined"];
const DEFAULTS = { view: "combined", max_grades: 5 };
const NEW_DAYS = 5;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const STRINGS = {
  cs: {
    title: "Známky",
    new: "nová",
    empty: "Zatím žádné známky",
    unavailable: "Známky nejsou dostupné",
    loading: "Načítám…",
    weight: "váha",
    decimal: ",",
    date: (day, month) => `${day}. ${month}.`,
    subject: "Předmět",
    average: "Ø",
    attendance: "Doch.",
    fold: (n) =>
      `${n} ${n === 1 ? "předmět" : n <= 4 ? "předměty" : "předmětů"} zatím bez známky`,
  },
  en: {
    title: "Grades",
    new: "new",
    empty: "No grades yet",
    unavailable: "Grades unavailable",
    loading: "Loading…",
    weight: "weight",
    decimal: ".",
    date: (day, month) => `${day} ${MONTHS[month - 1]}`,
    subject: "Subject",
    average: "Avg",
    attendance: "Att.",
    fold: (n) => `${n} ${n === 1 ? "subject" : "subjects"} without grades yet`,
  },
};

const STYLE = `
  :host { display: block; }
  ha-card { display: block; padding: 12px; }
  .card { color: var(--primary-text-color); --new: var(--edookit-new-color, #ff9800); }
  .head { display: flex; justify-content: space-between; align-items: center; gap: 8px;
    margin-bottom: 8px; }
  .title { font-size: 18px; font-weight: 600; }
  .status { font-size: 13px; color: var(--secondary-text-color); padding: 4px 0; }
  .mark { flex: none; display: inline-flex; align-items: center; justify-content: center;
    min-width: 24px; height: 24px; padding: 0 4px; box-sizing: border-box; border-radius: 6px;
    font-size: 13px; font-weight: 700; color: #fff; }
  .m1 { background: #43a047; } .m2 { background: #7cb342; }
  .m3 { background: #fbc02d; color: #212121; }
  .m4 { background: #fb8c00; } .m5 { background: #e53935; } .mx { background: #9e9e9e; }
  .big { display: flex; gap: 12px; align-items: center; padding: 10px; margin-bottom: 6px;
    border-radius: 10px; background: var(--secondary-background-color); }
  .big .mark { min-width: 48px; height: 48px; font-size: 26px; border-radius: 10px; }
  .big .topic { font-size: 15px; font-weight: 600; }
  .main { min-width: 0; flex: 1; }
  .topic { overflow-wrap: anywhere; }
  .meta { font-size: 12px; color: var(--secondary-text-color); }
  .new { margin-left: 6px; padding: 1px 7px; border-radius: 999px; font-size: 11px;
    font-weight: 600; background: var(--new); color: #fff; }
  .row { display: flex; gap: 10px; align-items: center; padding: 6px 0;
    border-top: 1px solid var(--divider-color); }
  .clickable { cursor: pointer; }
  .srow, .shead { display: flex; gap: 8px; align-items: center; padding: 5px 0;
    border-top: 1px solid var(--divider-color); }
  .shead { border-top: none; font-size: 12px; color: var(--secondary-text-color); }
  .short { flex: none; width: 56px; font-weight: 600; overflow: hidden; text-overflow: ellipsis;
    white-space: nowrap; }
  .marks { flex: 1; min-width: 0; display: flex; flex-wrap: wrap; gap: 4px; }
  .avg, .att { flex: none; width: 40px; text-align: right; font-size: 13px; }
  .none { color: var(--secondary-text-color); }
  .fold { font-size: 12px; color: var(--secondary-text-color); padding: 6px 0;
    border-top: 1px solid var(--divider-color); }
`;

function h(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined && text !== null) el.textContent = text;
  return el;
}

function userLanguage(hass) {
  const locale = hass && hass.locale && hass.locale.language;
  return typeof locale === "string" && locale.startsWith("cs") ? "cs" : "en";
}

function dayNumber(iso) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
  return match ? Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])) / 864e5 : null;
}

function dateLabel(t, iso) {
  const match = /^\d{4}-(\d{2})-(\d{2})/.exec(iso || "");
  return match ? t.date(Number(match[2]), Number(match[1])) : "";
}

function number(t, value, digits) {
  const text = digits === undefined ? String(value) : value.toFixed(digits);
  return text.replace(".", t.decimal);
}

function markEl(grade) {
  const value = grade.value;
  const colour = Number.isInteger(value) && value >= 1 && value <= 5 ? `m${value}` : "mx";
  return h("span", `mark ${colour}`, grade.mark);
}

class EdookitGradesCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  static getStubConfig(hass) {
    const entity = Object.keys((hass && hass.states) || {}).find(
      (id) => id.startsWith("sensor.edookit_") && id.endsWith("_latest_grade"),
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
    this._generation = 0;
    this._connection = null;
    this._onReady = () => {
      this._teardown();
      this._ensureSubscribed();
    };
    this._language = null;
    // Clicked grades hide their badge at once; the next push confirms it.
    this._seenHere = new Set();

    const style = h("style");
    style.textContent = STYLE;
    this._card = h("ha-card");
    this._body = h("div", "card");
    this._card.append(this._body);
    this.shadowRoot.append(style, this._card);
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("The edookit-grades-card needs an entity");
    }
    if (config.view !== undefined && !VIEWS.includes(config.view)) {
      throw new Error(`view must be one of ${VIEWS.join(", ")}`);
    }
    const max = config.max_grades;
    if (max !== undefined && !(Number.isInteger(max) && max > 0)) {
      throw new Error("max_grades must be a positive whole number");
    }
    const entityChanged = this._config !== null && this._config.entity !== config.entity;
    this._config = { ...DEFAULTS, ...config };
    if (entityChanged) {
      this._payload = null;
      this._seenHere.clear();
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
  }

  disconnectedCallback() {
    this._connected = false;
    this._unwatchConnection();
    this._teardown();
  }

  // Same reconnect handling as the other cards: subscribe with
  // resubscribe: false and redo it on "ready", or a restarting HA leaves the
  // card frozen on a rejected re-subscription.
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
        { type: "edookit/grades/subscribe", entity_id: this._config.entity },
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
    if (!Array.isArray(event.grades)) return;
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
    if (!this._config) return;
    this._language = this._resolveLanguage();
    const t = STRINGS[this._language];
    this._body.replaceChildren();
    const head = h("div", "head");
    head.append(h("span", "title", t.title));
    this._body.append(head);
    const payload = this._payload;
    if (!payload || !payload.available) {
      const waiting = !payload && this._retryTimer === null;
      this._body.append(h("div", "status", waiting ? t.loading : t.unavailable));
      return;
    }
    const view = this._config.view;
    if (view === "subjects") {
      this._renderSubjects(t, payload.subjects, true);
      return;
    }
    if (!payload.grades.length) {
      this._body.append(h("div", "status", t.empty));
      return;
    }
    if (view === "latest") {
      this._renderLatest(t, payload.grades.slice(0, this._config.max_grades));
      return;
    }
    this._renderLatest(t, payload.grades.slice(0, 1));
    const graded = payload.subjects.filter((subject) => subject.marks.length);
    this._renderSubjects(t, graded, false);
    const ungraded = payload.subjects.length - graded.length;
    if (ungraded) this._body.append(h("div", "fold", t.fold(ungraded)));
  }

  _isNew(grade) {
    if (grade.seen || this._seenHere.has(grade.id)) return false;
    const today = dayNumber(this._payload.today);
    const entered = dayNumber(grade.entered);
    return today !== null && entered !== null && today - entered < NEW_DAYS;
  }

  _markSeen(grade) {
    this._seenHere.add(grade.id);
    this._render();
    const message = {
      type: "edookit/grades/seen",
      entity_id: this._config.entity,
      grade_id: grade.id,
    };
    Promise.resolve(this._hass.callWS(message)).catch(() => {
      this._seenHere.delete(grade.id);
      this._render();
    });
  }

  _gradeElement(className, grade, isNew) {
    const el = h("div", isNew ? `${className} clickable` : className);
    el.setAttribute("data-id", String(grade.id));
    if (isNew) el.addEventListener("click", () => this._markSeen(grade));
    return el;
  }

  _topic(t, grade, isNew) {
    const line = h("div");
    line.append(h("span", "topic", grade.topic || grade.category));
    if (isNew) line.append(h("span", "new", t.new));
    return line;
  }

  _renderLatest(t, grades) {
    const [newest, ...rest] = grades;
    const newestIsNew = this._isNew(newest);
    const big = this._gradeElement("big", newest, newestIsNew);
    const main = h("div", "main");
    const details = [dateLabel(t, newest.entered), newest.teacher];
    if (newest.weight !== null && newest.weight !== undefined) {
      details.push(`${t.weight} ${number(t, newest.weight)}`);
    }
    main.append(
      this._topic(t, newest, newestIsNew),
      h("div", "meta", newest.subject || newest.category),
      h("div", "meta", details.filter(Boolean).join(" · ")),
    );
    big.append(markEl(newest), main);
    this._body.append(big);
    rest.forEach((grade) => {
      const isNew = this._isNew(grade);
      const row = this._gradeElement("row", grade, isNew);
      const body = h("div", "main");
      const label = grade.subject || grade.category;
      const meta = `${label} · ${dateLabel(t, grade.entered)}`;
      body.append(this._topic(t, grade, isNew), h("div", "meta", meta));
      row.append(markEl(grade), body);
      this._body.append(row);
    });
  }

  _renderSubjects(t, subjects, withAttendance) {
    if (withAttendance) {
      const head = h("div", "shead");
      head.append(
        h("span", "short", t.subject),
        h("span", "marks"),
        h("span", "avg", t.average),
        h("span", "att", t.attendance),
      );
      this._body.append(head);
    }
    subjects.forEach((subject) => {
      const row = h("div", "srow");
      const marks = h("span", "marks");
      if (subject.marks.length) subject.marks.forEach((grade) => marks.append(markEl(grade)));
      else marks.append(h("span", "none", "—"));
      const average = subject.average === null ? "—" : number(t, subject.average, 1);
      row.append(h("span", "short", subject.short), marks, h("span", "avg", average));
      if (withAttendance) {
        const attendance = subject.attendance;
        row.append(h("span", "att", attendance === null ? "—" : `${Math.round(attendance)} %`));
      }
      this._body.append(row);
    });
  }
}

const EDITOR_STRINGS = {
  cs: {
    labels: {
      entity: "Poslední známka",
      view: "Zobrazení",
      max_grades: "Počet známek",
      language: "Jazyk",
    },
    helpers: {
      language: "Bez výběru se řídí jazykem Home Assistantu.",
    },
    views: { latest: "Poslední", subjects: "Předměty", combined: "Poslední + předměty" },
  },
  en: {
    labels: {
      entity: "Latest grade",
      view: "View",
      max_grades: "Grades shown",
      language: "Language",
    },
    helpers: {
      language: "Leave empty to follow the Home Assistant language.",
    },
    views: { latest: "Latest", subjects: "Subjects", combined: "Latest + subjects" },
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
        { name: "max_grades", selector: { number: { min: 1, mode: "box" } } },
        {
          name: "language",
          selector: select([
            { value: "cs", label: "Čeština" },
            { value: "en", label: "English" },
          ]),
        },
      ],
    },
  ];
}

// Same scheme as the other editors: defaults filled in for ha-form, which
// would show a left-out option as empty, and dropped again on the way out.
class EdookitGradesCardEditor extends HTMLElement {
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
      .filter((entry) => entry.platform === "edookit" && entry.translation_key === "latest_grade")
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
    customElements.define(CARD_TAG, EdookitGradesCard);
  }
  if (!customElements.get(EDITOR_TAG)) {
    customElements.define(EDITOR_TAG, EdookitGradesCardEditor);
  }
});

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === CARD_TAG)) {
  window.customCards.push({
    type: CARD_TAG,
    name: "Edookit grades",
    description: "School grades from Edookit: the latest grade and an overview per subject",
  });
}
