// Renders the timetable card against a minimal fake DOM and prints what it shows.
// Input on stdin: {"config": {...}, "events": [payload, ...]}, pushed in order.
const fs = require("fs");
const path = require("path");
const { hasClass, loadCard } = require("./card_dom");

const script = path.join(__dirname, "../custom_components/edookit/frontend/edookit-timetable-card.js");
const defined = loadCard(script);

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
  if (input.now) card._clock = () => input.now;
  try {
    card.setConfig(input.config);
  } catch (err) {
    console.log(JSON.stringify({ error: err.message }));
    return;
  }
  card.connectedCallback();
  card.hass = hass;
  input.events.forEach((event) => push(event));
  card.disconnectedCallback();

  const root = card.shadowRoot;
  const codes = (name) =>
    root.findAll(hasClass(name)).map((tile) => tile.children[0].textContent);
  const titles = root.findAll(hasClass("title"));
  const grids = root.findAll(hasClass("grid"));
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
      periodHeads: root.findAll(hasClass("period-head")).length,
      columns: grids.length ? grids[0].style.gridTemplateColumns : null,
      rows: grids.length ? grids[0].style.gridTemplateRows : null,
      todayRows: root.findAll(hasClass("today-row")).map((band) => band.style.gridRow),
      cells: root.findAll(hasClass("cell")).map((cell) => [cell.style.gridRow, cell.style.gridColumn]),
      cardClass: root.findAll(hasClass("card"))[0].className,
      haCardClass: root.children.find((node) => node.tagName === "ha-card").className,
      now: codes("now"),
    }),
  );
}

main();
