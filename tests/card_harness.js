// Renders the timetable card against a minimal fake DOM and prints what it shows.
// Input on stdin: {"config": {...}, "events": [payload, ...]}, pushed in order.
const fs = require("fs");
const path = require("path");
const vm = require("vm");

class FakeNode {
  constructor(tag, text = "") {
    this.tagName = tag;
    this.className = "";
    this.children = [];
    this.attributes = {};
    this.style = {};
    this._text = text;
    this.parent = null;
  }

  get textContent() {
    return this._text + this.children.map((child) => child.textContent).join("");
  }

  set textContent(value) {
    this._text = String(value);
    this.children = [];
  }

  get isConnected() {
    return true;
  }

  append(...nodes) {
    nodes.forEach((node) => {
      const child = typeof node === "string" ? new FakeNode("#text", node) : node;
      child.parent = this;
      this.children.push(child);
    });
  }

  replaceChildren(...nodes) {
    this.children = [];
    this.append(...nodes);
  }

  remove() {
    if (this.parent) this.parent.children = this.parent.children.filter((c) => c !== this);
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  addEventListener() {}
  removeEventListener() {}
  focus() {}

  findAll(predicate) {
    const found = predicate(this) ? [this] : [];
    return found.concat(...this.children.map((child) => child.findAll(predicate)));
  }
}

const hasClass = (name) => (node) => node.className.split(" ").includes(name);

class FakeHTMLElement extends FakeNode {
  constructor() {
    super("custom");
  }

  attachShadow() {
    this.shadowRoot = new FakeNode("#shadow");
    return this.shadowRoot;
  }
}

const defined = new Map();
const context = vm.createContext({
  document: {
    createElement: (tag) => new FakeNode(tag),
    createTextNode: (text) => new FakeNode("#text", text),
  },
  HTMLElement: FakeHTMLElement,
  customElements: {
    whenDefined: () => Promise.resolve(),
    get: (tag) => defined.get(tag),
    define: (tag, cls) => defined.set(tag, cls),
  },
  setTimeout,
  clearTimeout,
});
context.window = context;

const script = path.join(__dirname, "../custom_components/edookit/frontend/edookit-timetable-card.js");
vm.runInContext(fs.readFileSync(script, "utf8"), context);

async function main() {
  const input = JSON.parse(fs.readFileSync(0, "utf8"));
  await Promise.resolve();
  const Card = defined.get("edookit-timetable-card");
  const card = new Card();
  let push = null;
  const hass = {
    states: {},
    locale: { language: "en" },
    connection: {
      subscribeMessage: (callback) => {
        push = callback;
        return Promise.resolve(() => {});
      },
      addEventListener() {},
      removeEventListener() {},
    },
  };
  card.setConfig(input.config);
  card.connectedCallback();
  card.hass = hass;
  input.events.forEach((event) => push(event));

  const root = card.shadowRoot;
  const titles = root.findAll(hasClass("title"));
  console.log(
    JSON.stringify({
      head: root.findAll(hasClass("head")).length > 0,
      title: titles.length ? titles[0].textContent : null,
      buttons: root.findAll((node) => node.tagName === "button" && hasClass("switch")(node.parent))
        .length,
      days: root
        .findAll(hasClass("day"))
        .map((day) => day.children.find((c) => c.tagName === "small").textContent),
      status: root.findAll(hasClass("status")).map((node) => node.textContent),
    }),
  );
}

main();
