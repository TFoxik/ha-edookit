// Renders the messages card against the fake DOM and prints its shadow tree.
// Input on stdin: {"config": {...}, "language": "cs", "events": [payload, ...],
// "ws": {"<message_id>": result | {"error": {...}}}, "clicks": [spec, ...]}.
// A click spec is "row:<id>" for a message row, or a class name (first match).
const fs = require("fs");
const path = require("path");
const { hasClass, loadCard } = require("./card_dom");

const script = path.join(__dirname, "../custom_components/edookit/frontend/edookit-messages-card.js");
const defined = loadCard(script);

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

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

function target(root, spec) {
  if (spec.startsWith("row:")) {
    const id = spec.slice(4);
    return root.findAll((n) => hasClass("row")(n) && n.attributes["data-id"] === id)[0];
  }
  return root.findAll(hasClass(spec))[0];
}

async function main() {
  const input = JSON.parse(fs.readFileSync(0, "utf8"));
  await Promise.resolve();
  const Card = defined.get("edookit-messages-card");
  const card = new Card();
  const calls = [];
  let push = null;
  const hass = {
    states: {},
    locale: { language: input.language || "cs" },
    callWS: (msg) => {
      calls.push(msg);
      const answer = (input.ws || {})[String(msg.message_id)];
      if (!answer || answer.error) return Promise.reject(answer ? answer.error : { code: "x" });
      return Promise.resolve(answer);
    },
    connection: {
      subscribeMessage: (callback) => {
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
      const node = target(card.shadowRoot, spec);
      if (!node) throw new Error(`no node for click ${spec}`);
      node.dispatch("click");
      await settle();
    }
  }
  console.log(JSON.stringify({ error, calls, tree: serialize(card.shadowRoot) }));
}

main();
