const CARD_TAG = "edookit-messages-card";
const EDITOR_TAG = "edookit-messages-card-editor";
const RETRY_MS = 30000;
const DEFAULT_MAX = 5;
const STYLES = ["classic", "minimal", "modern"];
const DEFAULTS = {
  style: "classic",
  open: "inline",
  max_messages: DEFAULT_MAX,
  unread_only: false,
  show_preview: true,
  compact: false,
  show_header: true,
};
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const STRINGS = {
  cs: {
    title: "Zprávy",
    badge: (n) => `${n} ${n === 1 ? "nepřečtená" : n <= 4 ? "nepřečtené" : "nepřečtených"}`,
    newBadge: (n) => `${n} ${n === 1 ? "nová" : n <= 4 ? "nové" : "nových"}`,
    empty: "Žádné zprávy",
    noUnread: "Žádné nepřečtené zprávy",
    yesterday: "včera",
    loading: "Načítám…",
    error: "Zprávu se nepodařilo načíst, zkuste to znovu.",
    adminOnly: "Zprávy může otevírat jen správce Home Assistantu.",
    unavailable: "Zprávy nejsou dostupné",
    from: "Od",
    to: "Komu",
    close: "Zavřít",
    date: (day, month) => `${day}. ${month}.`,
  },
  en: {
    title: "Messages",
    badge: (n) => `${n} unread`,
    newBadge: (n) => `${n} new`,
    empty: "No messages",
    noUnread: "No unread messages",
    yesterday: "yesterday",
    loading: "Loading…",
    error: "Couldn't load the message, try again.",
    adminOnly: "Only Home Assistant administrators can open messages.",
    unavailable: "Messages unavailable",
    from: "From",
    to: "To",
    close: "Close",
    date: (day, month) => `${day} ${MONTHS[month - 1]}`,
  },
};

// The body arrives as a node tree already reduced to these tags by pyedookit;
// the card checks again so it never depends on the library for its safety.
const BODY_TAGS = new Set(["p", "br", "strong", "em", "u", "ul", "ol", "li", "a"]);
const SAFE_HREF = /^https?:\/\//i;

const STYLE = `
  :host { display: block;
    --t-title: var(--edookit-font-title, 16px); --t-text: var(--edookit-font-text, 14px);
    --t-meta: var(--edookit-font-meta, 12px); --t-min: var(--edookit-font-min, 11px); }
  ha-card { display: block; padding: 12px; font-size: var(--t-text); }
  .card { color: var(--primary-text-color); --dot: var(--edookit-unread-color, #ff9800); }
  .head { display: flex; justify-content: space-between; align-items: center; gap: 8px;
    margin-bottom: 4px; }
  .title { font-size: var(--t-title); font-weight: 600; }
  .badge { font-size: var(--t-meta); padding: 2px 10px; border-radius: 999px; background: var(--dot);
    color: #fff; }
  .status { font-size: var(--t-meta); color: var(--secondary-text-color); margin-top: 4px; }
  .row { display: flex; gap: 8px; padding: 8px 0; cursor: pointer; outline: none; }
  .style-classic .row { border-top: 1px solid var(--divider-color); }
  .row:focus-visible { box-shadow: inset 0 0 0 2px var(--primary-color); }
  .dot { flex: none; width: 8px; height: 8px; margin-top: 6px; border-radius: 50%; }
  .row.unread .dot { background: var(--dot); }
  .main { min-width: 0; flex: 1; }
  .subject { overflow-wrap: anywhere; }
  .row.unread .subject { font-weight: 600; }
  .meta { font-size: var(--t-meta); color: var(--secondary-text-color); }
  .when { flex: none; font-size: var(--t-meta); color: var(--secondary-text-color); }
  .preview { font-size: var(--t-meta); color: var(--secondary-text-color); margin-top: 2px;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .message { line-height: 1.45; overflow-wrap: anywhere; }
  .inline { margin: 0 0 8px 16px; padding: 4px 0 4px 10px; border-left: 3px solid var(--dot); }
  .message .meta { margin-bottom: 6px; }
  .message p { margin: 0 0 8px; }
  .message ul, .message ol { margin: 0 0 8px; padding-left: 20px; }
  .message a { color: var(--primary-color); }
  .compact .head { margin-bottom: 0; }
  .compact .row { padding: 4px 0; }
  .compact .preview { margin-top: 0; }
  .style-minimal .badge { background: none; color: var(--dot); padding: 0; font-weight: 600; }
  .style-minimal .row { align-items: center; padding: 5px 0; }
  .style-minimal .dot { width: 6px; height: 6px; margin-top: 0; }
  .style-minimal .subject { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden;
    text-overflow: ellipsis; }
  .style-minimal.compact .row { padding: 2px 0; }
  .style-modern .head { margin-bottom: 10px; }
  .style-modern .row { gap: 10px; padding: 10px; margin-bottom: 8px;
    border-radius: 14px; background: var(--secondary-background-color); }
  .style-modern .row.unread { box-shadow: inset 3px 0 0 var(--dot);
    background: color-mix(in srgb, var(--dot) 8%, var(--secondary-background-color)); }
  .style-modern.compact .row { padding: 6px 8px; margin-bottom: 4px; }
  .avatar { flex: none; width: 2.4em; height: 2.4em; border-radius: 50%; display: flex;
    align-items: center; justify-content: center; font-weight: 600; }
  .style-modern.compact .avatar { font-size: var(--t-meta); }
  .top { display: flex; justify-content: space-between; gap: 6px; }
  .sender { font-weight: 600; min-width: 0; overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap; }
  .style-modern .preview { white-space: normal; display: -webkit-box; -webkit-line-clamp: 2;
    -webkit-box-orient: vertical; }
  .style-modern .inline { margin-left: 44px; }
  .error { color: var(--error-color, #db4437); }
  .overlay { position: fixed; inset: 0; z-index: 10; box-sizing: border-box; padding: 16px;
    display: flex; align-items: center; justify-content: center; background: rgba(0, 0, 0, 0.45); }
  .panel { box-sizing: border-box; width: 100%; max-width: 560px; max-height: 100%;
    overflow: auto; padding: 14px 16px; border-radius: 12px; outline: none;
    border: 1px solid var(--divider-color);
    background: var(--card-background-color, #fff); color: var(--primary-text-color);
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25); font-size: var(--t-text); }
  .panel h4 { margin: 0 0 2px; font-size: var(--t-title); line-height: 1.25; overflow-wrap: anywhere; }
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

// Sent times carry the portal's own offset, so the wall-clock parts are read
// as written rather than converted to the viewer's zone.
function parseSent(iso) {
  const match = /^((\d{4})-(\d{2})-(\d{2}))T(\d{2}):(\d{2})/.exec(iso || "");
  if (!match) return null;
  const [, day, , month, date, hour, minute] = match;
  return { day, month: Number(month), date: Number(date), time: `${Number(hour)}:${minute}` };
}

function sentLabel(t, iso) {
  const sent = parseSent(iso);
  return sent ? `${t.date(sent.date, sent.month)} ${sent.time}` : "";
}

function previousDay(day) {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, date - 1)).toISOString().slice(0, 10);
}

function userLanguage(hass) {
  const locale = hass && hass.locale && hass.locale.language;
  return typeof locale === "string" && locale.startsWith("cs") ? "cs" : "en";
}

// Today's messages show the time, yesterday's a word, older ones the date.
function shortLabel(t, iso, days) {
  const sent = parseSent(iso);
  if (!sent) return "";
  if (sent.day === days.today) return sent.time;
  if (sent.day === days.yesterday) return t.yesterday;
  return t.date(sent.date, sent.month);
}

// Academic titles end with a dot ("Mgr.", "Ing."); initials skip them.
function initials(sender) {
  const words = (sender || "").split(/\s+/).filter((w) => w && !w.endsWith("."));
  if (!words.length) return "?";
  const first = words[0][0];
  const last = words.length > 1 ? words[words.length - 1][0] : "";
  return (first + last).toUpperCase();
}

function hue(text) {
  let hash = 0;
  for (const ch of text || "") hash = (hash * 31 + ch.codePointAt(0)) % 360;
  return hash;
}

function appendBody(parent, nodes) {
  (Array.isArray(nodes) ? nodes : []).forEach((node) => {
    if (!node || typeof node !== "object") return;
    if (typeof node.text === "string") {
      parent.append(node.text);
      return;
    }
    const children = node.children;
    if (!BODY_TAGS.has(node.tag) || (node.tag === "a" && !SAFE_HREF.test(node.href || ""))) {
      appendBody(parent, children);
      return;
    }
    const el = h(node.tag);
    if (node.tag === "a") {
      el.setAttribute("href", node.href);
      el.setAttribute("target", "_blank");
      el.setAttribute("rel", "noopener noreferrer");
    }
    if (node.tag !== "br") appendBody(el, children);
    parent.append(el);
  });
}

class EdookitMessagesCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  static getStubConfig(hass) {
    const entity = Object.keys((hass && hass.states) || {}).find(
      (id) => id.startsWith("sensor.edookit_") && id.endsWith("_unread_messages"),
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
    this._openId = null;
    this._opened = null;
    this._overlay = null;
    this._overlayContent = null;
    this._onKey = (e) => {
      if (e.key === "Escape") this._close();
    };

    const style = h("style");
    style.textContent = STYLE;
    this._card = h("ha-card");
    this._body = h("div", "card");
    this._card.append(this._body);
    this.shadowRoot.append(style, this._card);
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("The edookit-messages-card needs an entity");
    }
    checkFontSizes(config.font_sizes);
    if (config.open !== undefined && config.open !== "inline" && config.open !== "popup") {
      throw new Error("open must be inline or popup");
    }
    if (config.style !== undefined && !STYLES.includes(config.style)) {
      throw new Error(`style must be one of ${STYLES.join(", ")}`);
    }
    const max = config.max_messages;
    if (max !== undefined && !(Number.isInteger(max) && max > 0)) {
      throw new Error("max_messages must be a positive whole number");
    }
    const entityChanged = this._config !== null && this._config.entity !== config.entity;
    this._config = { ...DEFAULTS, ...config };
    applyFontSizes(this, config.font_sizes);
    if (entityChanged) {
      this._payload = null;
      this._close();
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
    return 5;
  }

  connectedCallback() {
    this._connected = true;
    this._watchConnection();
    this._ensureSubscribed();
  }

  disconnectedCallback() {
    this._connected = false;
    this._close();
    this._unwatchConnection();
    this._teardown();
  }

  // Same reconnect handling as the timetable card: subscribe with
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
        { type: "edookit/messages/subscribe", entity_id: this._config.entity },
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
    if (!Array.isArray(event.messages)) return;
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

  get _popup() {
    return this._config.open === "popup";
  }

  _render() {
    if (!this._config) return;
    this._language = this._resolveLanguage();
    const t = STRINGS[this._language];
    const { style } = this._config;
    this._body.replaceChildren();
    this._body.className = `card style-${style}${this._config.compact ? " compact" : ""}`;
    const payload = this._payload;
    if (!payload) {
      this._body.append(h("div", "status", this._retryTimer !== null ? t.unavailable : t.loading));
      return;
    }
    if (this._overlay) this._fillOpened(this._overlayContent, t);
    if (this._config.show_header !== false) {
      const head = h("div", "head");
      head.append(h("div", "title", t.title));
      if (payload.unread > 0) {
        const badges = { classic: t.badge, minimal: t.newBadge, modern: String };
        head.append(h("div", "badge", badges[style](payload.unread)));
      }
      this._body.append(head);
    }
    if (payload.available === false) {
      this._body.append(h("div", "status", t.unavailable));
      return;
    }
    const unreadOnly = Boolean(this._config.unread_only);
    const messages = unreadOnly ? payload.messages.filter((m) => m.unread) : payload.messages;
    if (!messages.length) {
      this._body.append(h("div", "status", unreadOnly ? t.noUnread : t.empty));
      return;
    }
    const today = payload.today || "";
    const days = { today, yesterday: today && previousDay(today) };
    messages.slice(0, this._config.max_messages).forEach((summary) => {
      this._body.append(this._renderRow(summary, t, style, days));
      if (!this._popup && summary.id === this._openId) {
        const view = h("div", "inline");
        this._fillOpened(view, t);
        this._body.append(view);
      }
    });
  }

  _renderRow(summary, t, style, days) {
    const row = h("div", summary.unread ? "row unread" : "row");
    row.setAttribute("data-id", String(summary.id));
    row.setAttribute("role", "button");
    row.setAttribute("aria-expanded", String(summary.id === this._openId));
    row.tabIndex = 0;
    row.addEventListener("click", () => this._toggle(summary.id));
    row.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        this._toggle(summary.id);
      }
    });
    const when = h("span", "when", shortLabel(t, summary.sent, days));
    if (style === "minimal") {
      row.append(h("div", "dot"), h("span", "subject", summary.subject), when);
      return row;
    }
    const main = h("div", "main");
    if (style === "modern") {
      const avatar = h("div", "avatar", initials(summary.sender));
      const tone = hue(summary.sender);
      avatar.style.background = `hsl(${tone} 30% 32%)`;
      avatar.style.color = `hsl(${tone} 80% 88%)`;
      const top = h("div", "top");
      top.append(h("span", "sender", summary.sender), when);
      main.append(top, h("div", "subject", summary.subject));
      row.append(avatar, main);
    } else {
      main.append(
        h("div", "subject", summary.subject),
        h("div", "meta", `${summary.sender} · ${sentLabel(t, summary.sent)}`),
      );
      row.append(h("div", "dot"), main);
    }
    if (this._config.show_preview !== false && (summary.id !== this._openId || this._popup)) {
      main.append(h("div", "preview", summary.preview));
    }
    return row;
  }

  _fillOpened(container, t) {
    container.replaceChildren();
    const opened = this._opened;
    if (!opened || opened.id !== this._openId) return;
    if (opened.state === "loading") {
      container.append(h("div", "status", t.loading));
    } else if (opened.state === "error") {
      container.append(h("div", "error", opened.code === "unauthorized" ? t.adminOnly : t.error));
    } else {
      container.append(this._renderMessage(opened.message, t));
    }
  }

  _renderMessage(message, t) {
    const view = h("div", "message");
    if (this._popup) view.append(h("h4", "", message.subject));
    view.append(
      h(
        "div",
        "meta",
        `${t.from}: ${message.sender} · ${t.to}: ${message.recipients} · ${sentLabel(t, message.sent)}`,
      ),
    );
    const text = h("div", "text");
    appendBody(text, message.body);
    view.append(text);
    return view;
  }

  _toggle(id) {
    const failed = this._opened && this._opened.id === id && this._opened.state === "error";
    if (!this._popup && this._openId === id && !failed) {
      this._close();
      return;
    }
    this._openId = id;
    this._opened = { id, state: "loading" };
    if (this._popup) this._openOverlay();
    this._render();
    this._load(id);
  }

  _load(id) {
    const done = (opened) => {
      if (this._openId !== id) return;
      this._opened = opened;
      this._render();
    };
    Promise.resolve()
      .then(() =>
        this._hass.callWS({
          type: "edookit/messages/get",
          entity_id: this._config.entity,
          message_id: id,
        }),
      )
      .then(
        (message) => done({ id, state: "loaded", message }),
        (err) => done({ id, state: "error", code: err && err.code }),
      );
  }

  _openOverlay() {
    if (this._overlay) return;
    const t = STRINGS[this._resolveLanguage()];
    const overlay = h("div", "overlay");
    const panel = h("div", "panel");
    panel.tabIndex = -1;
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    const content = h("div");
    const close = h("button", "close", t.close);
    close.type = "button";
    close.addEventListener("click", () => this._close());
    panel.append(content, close);
    overlay.append(panel);
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) this._close();
    });
    overlay.addEventListener("keydown", this._onKey);
    this._overlay = overlay;
    this._overlayContent = content;
    this.shadowRoot.append(overlay);
    panel.focus();
  }

  _close() {
    this._openId = null;
    this._opened = null;
    if (this._overlay) {
      this._overlay.remove();
      this._overlay = null;
      this._overlayContent = null;
    }
    if (this._config) this._render();
  }
}

const EDITOR_STRINGS = {
  cs: {
    labels: {
      entity: "Nepřečtené zprávy",
      style: "Vzhled",
      open: "Otevřít zprávu",
      max_messages: "Počet zpráv",
      language: "Jazyk",
      unread_only: "Jen nepřečtené",
      show_preview: "Náhled textu",
      compact: "Úsporné řádky",
      show_header: "Záhlaví",
    },
    helpers: {
      language: "Bez výběru se řídí jazykem Home Assistantu.",
    },
    styles: { classic: "Klasický", minimal: "Minimální", modern: "Moderní" },
    opens: { inline: "V kartě", popup: "V okně" },
  },
  en: {
    labels: {
      entity: "Unread messages",
      style: "Style",
      open: "Open a message",
      max_messages: "Messages shown",
      language: "Language",
      unread_only: "Unread only",
      show_preview: "Text preview",
      compact: "Compact rows",
      show_header: "Header",
    },
    helpers: {
      language: "Leave empty to follow the Home Assistant language.",
    },
    styles: { classic: "Classic", minimal: "Minimal", modern: "Modern" },
    opens: { inline: "In the card", popup: "In a popup" },
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
          name: "open",
          selector: select(["inline", "popup"].map((value) => ({ value, label: t.opens[value] }))),
        },
        { name: "max_messages", selector: { number: { min: 1, mode: "box" } } },
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
      schema: ["unread_only", "show_preview", "compact", "show_header"].map((name) => ({
        name,
        selector: { boolean: {} },
      })),
    },
  ];
}

// Same scheme as the timetable editor: defaults filled in for ha-form, which
// would show a left-out option as off, and dropped again on the way out.
class EdookitMessagesCardEditor extends HTMLElement {
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
      .filter((entry) => entry.platform === "edookit" && entry.translation_key === "unread_messages")
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
    customElements.define(CARD_TAG, EdookitMessagesCard);
  }
  if (!customElements.get(EDITOR_TAG)) {
    customElements.define(EDITOR_TAG, EdookitMessagesCardEditor);
  }
});

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === CARD_TAG)) {
  window.customCards.push({
    type: CARD_TAG,
    name: "Edookit messages",
    description: "School messages from Edookit: unread count, list, and the full text on tap",
  });
}
