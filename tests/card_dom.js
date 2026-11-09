// A minimal fake DOM for running the cards under node, shared by the card harnesses.
const fs = require("fs");
const vm = require("vm");

class FakeStyle {
  _props = {};

  setProperty(name, value) {
    this._props[name] = String(value);
  }

  removeProperty(name) {
    delete this._props[name];
  }
}

class FakeNode {
  constructor(tag, text = "") {
    this.tagName = tag;
    this.className = "";
    this.children = [];
    this.attributes = {};
    this.style = new FakeStyle();
    this._text = text;
    this.parent = null;
    this.listeners = {};
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

  addEventListener(type, listener) {
    (this.listeners[type] = this.listeners[type] || []).push(listener);
  }

  removeEventListener(type, listener) {
    this.listeners[type] = (this.listeners[type] || []).filter((l) => l !== listener);
  }

  dispatch(type, extra = {}) {
    const event = { type, target: this, preventDefault() {}, stopPropagation() {}, ...extra };
    (this.listeners[type] || []).slice().forEach((listener) => listener(event));
  }

  dispatchEvent(event) {
    this.dispatch(event.type, event);
    return true;
  }

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

function loadCard(script, timers = {}) {
  const defined = new Map();
  const context = vm.createContext({
    document: {
      createElement: (tag) => new FakeNode(tag),
      createTextNode: (text) => new FakeNode("#text", text),
    },
    HTMLElement: FakeHTMLElement,
    CustomEvent: class {
      constructor(type, init = {}) {
        this.type = type;
        this.detail = init.detail;
      }
    },
    customElements: {
      whenDefined: () => Promise.resolve(),
      get: (tag) => defined.get(tag),
      define: (tag, cls) => defined.set(tag, cls),
    },
    setTimeout: timers.setTimeout || setTimeout,
    clearTimeout: timers.clearTimeout || clearTimeout,
  });
  context.window = context;
  vm.runInContext(fs.readFileSync(script, "utf8"), context);
  return defined;
}

const settle = () => new Promise((resolve) => setImmediate(resolve));

// Text set through textContent is serialized as a #text child, as the browser makes it.
function serialize(node) {
  if (node.tagName === "#text") return { tag: "#text", text: node._text };
  const text = node.tagName === "style" || !node._text ? [] : [{ tag: "#text", text: node._text }];
  return {
    tag: node.tagName,
    cls: node.className,
    attrs: node.attributes,
    children: [...text, ...node.children.map(serialize)],
  };
}

// Fake timers for loadCard; fire(ms) runs the ones due within ms.
function fakeTimers() {
  let nextId = 1;
  const pending = new Map();
  return {
    setTimeout: (fn, delay) => {
      const id = nextId++;
      pending.set(id, { fn, delay });
      return id;
    },
    clearTimeout: (id) => pending.delete(id),
    delays: () => [...pending.values()].map((timer) => timer.delay),
    fire: (ms) =>
      [...pending.entries()]
        .filter(([, timer]) => timer.delay <= ms)
        .forEach(([id, timer]) => {
          pending.delete(id);
          timer.fn();
        }),
  };
}

module.exports = { FakeNode, fakeTimers, hasClass, loadCard, serialize, settle };
