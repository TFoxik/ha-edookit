// Renders the grades card against the fake DOM and prints its shadow tree.
// Input on stdin: {"config": {...}, "language": "cs", "events": [payload, ...],
// "clicks": ["grade:<id>", ...]}. "ws" in the output lists the callWS messages.
const fs = require("fs");
const path = require("path");
const { loadCard } = require("./card_dom");

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

const script = path.join(__dirname, "../custom_components/edookit/frontend/edookit-grades-card.js");
const defined = loadCard(script);

function serialize(node) {
  if (node.tagName === "#text") return { tag: "#text", text: node._text };
  return {
    tag: node.tagName,
    cls: node.className,
    attrs: node.attributes,
    text: node.tagName === "style" ? "" : node._text,
    children: node.children.map(serialize),
  };
}

async function main() {
  const input = JSON.parse(fs.readFileSync(0, "utf8"));
  await Promise.resolve();
  const Card = defined.get("edookit-grades-card");
  const card = new Card();
  const calls = [];
  const ws = [];
  let push = null;
  const hass = {
    states: {},
    locale: { language: input.language || "cs" },
    callWS: (msg) => {
      ws.push(msg);
      return Promise.resolve(null);
    },
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
  if (error === null) {
    card.connectedCallback();
    card.hass = hass;
    (input.events || []).forEach((event) => push(event));
    for (const spec of input.clicks || []) {
      const id = spec.replace("grade:", "");
      const node = card.shadowRoot.findAll((n) => n.attributes["data-id"] === id)[0];
      if (!node) throw new Error(`no node for click ${spec}`);
      node.dispatch("click");
      await settle();
    }
  }
  console.log(JSON.stringify({ error, calls, ws, tree: serialize(card.shadowRoot) }));
}

main();
