// Renders the timetable card against a minimal fake DOM and prints what it shows.
// Input on stdin: {"config": {...}, "events": [week payload, ...], "homework_events": [payload, ...],
// "now": "HH:MM", "now_ms": epoch ms, "hass_before_config": bool, "click": "<class>", "reconnect": bool, "config_after": {...},
// "advance_ms": n}. Week and homework payloads go to the callback of their subscription type.
// "click" presses the tile that holds an element of that class and prints the opened detail.
// Timers are fake: advance_ms moves the clock and fires the timers due within it.
const fs = require("fs");
const path = require("path");
const { fakeTimers, hasClass, loadCard, serialize, settle } = require("./card_dom");

const timers = fakeTimers();

const script = path.join(__dirname, "../custom_components/edookit/frontend/edookit-timetable-card.js");
const defined = loadCard(script, timers);

const delays = timers.delays;

async function main() {
  const input = JSON.parse(fs.readFileSync(0, "utf8"));
  await Promise.resolve();
  const Card = defined.get("edookit-timetable-card");
  const card = new Card();
  const callbacks = {};
  const subscribed = [];
  const entities = [];
  const unsubscribed = [];
  const ready = [];
  const hass = {
    states: {},
    locale: { language: "en" },
    connection: {
      subscribeMessage: (callback, msg) => {
        subscribed.push(msg.type);
        entities.push(msg.entity_id);
        callbacks[msg.type] = callback;
        return Promise.resolve(() => {
          unsubscribed.push(msg.type);
        });
      },
      addEventListener: (type, listener) => {
        if (type === "ready") ready.push(listener);
      },
      removeEventListener: (type, listener) => {
        const at = ready.indexOf(listener);
        if (type === "ready" && at >= 0) ready.splice(at, 1);
      },
    },
  };
  let nowMs = input.now_ms;
  if (input.now) card._clock = () => input.now;
  if (nowMs !== undefined) card._nowMs = () => nowMs;
  if (input.hass_before_config) card.hass = hass;
  try {
    card.setConfig(input.config);
  } catch (err) {
    console.log(JSON.stringify({ error: err.message }));
    return;
  }
  card.connectedCallback();
  card.hass = hass;
  await settle();
  const feed = (type, events) =>
    (events || []).forEach((event) => callbacks[type] && callbacks[type](event));
  feed("edookit/week/subscribe", input.events);
  feed("edookit/homework/subscribe", input.homework_events);
  const scheduled = delays();
  if (input.reconnect) {
    ready.slice().forEach((listener) => listener());
    await settle();
    feed("edookit/week/subscribe", input.events);
    feed("edookit/homework/subscribe", input.homework_events);
  }
  if (input.config_after) {
    card.setConfig(input.config_after);
    await settle();
  }
  let detail = null;
  if (input.click) {
    const tile = card.shadowRoot.findAll(
      (n) => n.tagName === "button" && n.findAll(hasClass(input.click)).length > 0,
    )[0];
    if (!tile) throw new Error(`no tile holding ${input.click}`);
    tile.dispatch("click");
    const overlay = card.shadowRoot.findAll(hasClass("overlay"))[0];
    detail = overlay ? serialize(overlay) : null;
  }
  if (input.advance_ms) {
    if (nowMs !== undefined) nowMs += input.advance_ms;
    timers.fire(input.advance_ms);
  }
  const live = delays();
  card.disconnectedCallback();
  await settle();

  const root = card.shadowRoot;
  const codes = (name) =>
    root.findAll(hasClass(name)).map((tile) => tile.children[0].textContent);
  const dayLabel = (row) =>
    root
      .findAll((node) => hasClass("day")(node) && node.style.gridRow === row)
      .map((day) => day.children.find((c) => c.tagName === "small").textContent)[0] || null;
  const markers = root.findAll(hasClass("cell")).flatMap((cell) =>
    cell.findAll(hasClass("hw")).map((mark) => {
      const tile = cell.findAll((n) => n.tagName === "button" && n.findAll((m) => m === mark).length)[0];
      return {
        day: dayLabel(cell.style.gridRow),
        code: tile.children[0].textContent,
        column: cell.style.gridColumn,
        cls: mark.className,
      };
    }),
  );
  const titles = root.findAll(hasClass("title"));
  const grids = root.findAll(hasClass("grid"));
  console.log(
    JSON.stringify({
      head: root.findAll(hasClass("head")).length > 0,
      title: titles.length ? titles[0].textContent : null,
      names: root.findAll(hasClass("name")).map((node) => node.textContent),
      buttons: root.findAll((node) => node.tagName === "button" && hasClass("switch")(node.parent))
        .length,
      days: root
        .findAll(hasClass("day"))
        .map((day) => day.children.find((c) => c.tagName === "small").textContent),
      status: root.findAll(hasClass("status")).map((node) => node.textContent),
      periodHeads: root.findAll(hasClass("period-head")).length,
      columns: grids.length ? grids[0].style.gridTemplateColumns : null,
      rows: grids.length ? grids[0].style.gridTemplateRows : null,
      todayRows: root.findAll(hasClass("today-row")).map((band) => band.style.gridRow),
      cells: root.findAll(hasClass("cell")).map((cell) => [cell.style.gridRow, cell.style.gridColumn]),
      cardClass: root.findAll(hasClass("card"))[0].className,
      haCardClass: root.children.find((node) => node.tagName === "ha-card").className,
      now: codes("now"),
      markers,
      subscribed,
      entities,
      unsubscribed,
      detail,
      scheduled,
      live,
      pending: delays(),
    }),
  );
}

main();
