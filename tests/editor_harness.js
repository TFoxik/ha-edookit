// Drives a card's visual editor against the fake DOM and prints what ha-form gets.
// Input on stdin: {"card": "timetable" | "messages" | "grades", "config": {...}, "language": "cs",
// "entities": [{entity_id, platform, translation_key}, ...], "change": {...} | null}.
// "change" holds the fields edited in the form; the editor's answer is printed.
const fs = require("fs");
const path = require("path");
const { loadCard } = require("./card_dom");

async function main() {
  const input = JSON.parse(fs.readFileSync(0, "utf8"));
  const tag = `edookit-${input.card}-card`;
  const defined = loadCard(
    path.join(__dirname, `../custom_components/edookit/frontend/${tag}.js`),
  );
  await Promise.resolve();
  const editorTag = defined.get(tag).getConfigElement().tagName;
  const editor = new (defined.get(editorTag))();
  let changed = null;
  editor.addEventListener("config-changed", (e) => {
    changed = e.detail.config;
  });
  editor.setConfig(input.config);
  editor.hass = {
    locale: { language: input.language },
    entities: Object.fromEntries((input.entities || []).map((e) => [e.entity_id, e])),
  };
  const form = editor.children.find((node) => node.tagName === "ha-form");
  if (input.change) {
    form.dispatch("value-changed", { detail: { value: { ...form.data, ...input.change } } });
  }

  const fields = [];
  const walk = (schema) =>
    schema.forEach((field) => (field.type === "grid" ? walk(field.schema) : fields.push(field)));
  walk(form.schema);
  console.log(
    JSON.stringify({
      editorTag,
      data: form.data,
      fields: fields.map((field) => field.name),
      entities: fields.find((field) => field.name === "entity").selector.entity.include_entities,
      labels: Object.fromEntries(fields.map((field) => [field.name, form.computeLabel(field)])),
      changed,
    }),
  );
}

main();
