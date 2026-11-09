// Renders the homework card against the fake DOM and prints its shadow tree.
// Input on stdin: {"config": {...}, "language": "cs", "now": epoch ms, "events": [payload, ...],
// "clicks": ["click:<class>" | "key:<class>:<key>", ...], "advance_ms": n, "disconnect": bool}.
// With advance_ms the output also says whether the timer rebuilt the card body.
// Text set through textContent is printed as a #text child, as the browser makes it.
// Timers are fake: advance_ms moves the card's clock and fires the timers due within it.
const fs = require("fs");
const path = require("path");
const { fakeTimers, loadCard, serialize, settle } = require("./card_dom");

const timers = fakeTimers();

const script = path.join(__dirname, "../custom_components/edookit/frontend/edookit-homework-card.js");
const defined = loadCard(script, timers);

const delays = timers.delays;

async function main() {
  const input = JSON.parse(fs.readFileSync(0, "utf8"));
  await Promise.resolve();
  const Card = defined.get("edookit-homework-card");
  const card = new Card();
  let now = input.now;
  card._clock = () => now;
  const calls = [];
  let push = null;
  const hass = {
    states: {},
    locale: { language: input.language || "cs" },
    callWS: () => Promise.resolve(null),
    connection: {
      subscribeMessage: (callback, msg) => {
        calls.push(msg);
        push = callback;
        return Promise.resolve(() => {});
      },
      addEventListener() {},
      removeEventListener() {},
    },
  };
  let error = null;
  try {
    card.setConfig(input.config);
  } catch (err) {
    error = err.message;
  }
  let scheduled = [];
  let rebuilt = null;
  if (error === null) {
    card.connectedCallback();
    card.hass = hass;
    (input.events || []).forEach((event) => push(event));
    scheduled = delays();
    for (const spec of input.clicks || []) {
      const [kind, cls, key] = spec.split(":");
      const node = card.shadowRoot.findAll((n) => n.className.split(" ").includes(cls))[0];
      if (!node) throw new Error(`no node for ${spec}`);
      node.dispatch(kind === "key" ? "keydown" : "click", kind === "key" ? { key } : {});
      await settle();
    }
    if (input.advance_ms) {
      const before = card._body.children.slice();
      now += input.advance_ms;
      timers.fire(input.advance_ms);
      rebuilt = card._body.children.some((node, i) => node !== before[i]);
    }
    if (input.disconnect) card.disconnectedCallback();
  }
  console.log(
    JSON.stringify({ error, calls, scheduled, pending: delays(), rebuilt, tree: serialize(card.shadowRoot) }),
  );
}

main();
