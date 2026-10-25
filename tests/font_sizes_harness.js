// Configures one card and prints the font-size variables set on its host.
// Input on stdin: {"script": path, "tag": element name, "configs": [config, ...]}, applied in order.
const fs = require("fs");
const { loadCard } = require("./card_dom");

async function main() {
  const input = JSON.parse(fs.readFileSync(0, "utf8"));
  const defined = loadCard(input.script);
  await Promise.resolve();
  const Card = defined.get(input.tag);
  const card = new Card();
  let error = null;
  try {
    input.configs.forEach((config) => card.setConfig(config));
  } catch (err) {
    error = err.message;
  }
  // The timetable's clock timer would keep node running.
  card.disconnectedCallback();
  console.log(JSON.stringify({ error, host: card.style._props }));
}

main();
