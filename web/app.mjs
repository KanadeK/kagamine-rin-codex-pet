import {
  CELL_HEIGHT,
  CELL_WIDTH,
  assertTimeline,
  directionFrame,
  frameAt,
  timelineEventAt,
} from "./runtime.mjs";

const canvas = document.querySelector("#pet-canvas");
const context = canvas.getContext("2d", { alpha: true });
const stage = document.querySelector("#stage");
const stateLabel = document.querySelector("#state-label");
const eventLabel = document.querySelector("#event-label");
const playButton = document.querySelector("#play");
const speedSelect = document.querySelector("#speed");
const timelineList = document.querySelector("#timeline-list");
const status = document.querySelector("#load-status");
const stateButtons = [...document.querySelectorAll("[data-state]")];

const image = new Image();
image.decoding = "async";
image.src = "./pet/spritesheet.webp";

let timeline;
let playing = true;
let manualState = null;
let traceStartedAt = performance.now();
let pausedElapsed = 0;
let speed = 1;
let look = null;
let lookUntil = 0;
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

function drawCell({ row, column }) {
  context.clearRect(0, 0, CELL_WIDTH, CELL_HEIGHT);
  context.drawImage(
    image,
    column * CELL_WIDTH,
    row * CELL_HEIGHT,
    CELL_WIDTH,
    CELL_HEIGHT,
    0,
    0,
    CELL_WIDTH,
    CELL_HEIGHT,
  );
}

function updateLabels(event, state, frame) {
  stateLabel.textContent = state;
  eventLabel.textContent = event
    ? `${event.kind} · line ${event.sourceLine} · ${frame.column + 1}`
    : `manual preview · frame ${frame.column + 1}`;
  canvas.setAttribute(
    "aria-label",
    `Kagamine Rin pet, ${state}, frame ${frame.column + 1}`,
  );
}

function render(now) {
  if (!image.complete || !timeline) {
    requestAnimationFrame(render);
    return;
  }
  const elapsed = playing
    ? pausedElapsed + (now - traceStartedAt) * speed
    : pausedElapsed;
  const event = manualState ? null : timelineEventAt(timeline.events, elapsed);
  const state = manualState || event?.state || "idle";
  const frame =
    look && now < lookUntil
      ? look
      : frameAt(state, elapsed, reducedMotion || !playing);
  drawCell(frame);
  updateLabels(event, look && now < lookUntil ? `look ${look.direction}` : state, frame);
  requestAnimationFrame(render);
}

function renderTimeline(events) {
  timelineList.replaceChildren();
  for (const event of events) {
    const item = document.createElement("li");
    const time = document.createElement("time");
    time.textContent = `${(event.offsetMs / 1000).toFixed(2)}s`;
    const kind = document.createElement("code");
    kind.textContent = event.kind;
    const state = document.createElement("span");
    state.textContent = event.state;
    item.append(time, kind, state);
    timelineList.append(item);
  }
}

stage.addEventListener("pointermove", (event) => {
  const bounds = canvas.getBoundingClientRect();
  const centerX = bounds.left + bounds.width / 2;
  const centerY = bounds.top + bounds.height / 2;
  look = directionFrame(event.clientX - centerX, event.clientY - centerY, 32);
  lookUntil = Number.POSITIVE_INFINITY;
});

stage.addEventListener("pointerleave", () => {
  lookUntil = 0;
});

playButton.addEventListener("click", () => {
  const now = performance.now();
  if (playing) {
    pausedElapsed += (now - traceStartedAt) * speed;
  } else {
    traceStartedAt = now;
  }
  playing = !playing;
  playButton.textContent = playing ? "Pause trace" : "Play trace";
  playButton.setAttribute("aria-pressed", String(playing));
});

speedSelect.addEventListener("change", () => {
  const now = performance.now();
  if (playing) {
    pausedElapsed += (now - traceStartedAt) * speed;
    traceStartedAt = now;
  }
  speed = Number(speedSelect.value);
});

for (const button of stateButtons) {
  button.addEventListener("click", () => {
    const selected = button.dataset.state;
    manualState = manualState === selected ? null : selected;
    for (const candidate of stateButtons) {
      candidate.setAttribute(
        "aria-pressed",
        String(candidate.dataset.state === manualState),
      );
    }
  });
}

Promise.all([
  image.decode(),
  fetch("./timeline.json").then((response) => {
    if (!response.ok) throw new Error(`timeline HTTP ${response.status}`);
    return response.json();
  }),
])
  .then(([, value]) => {
    timeline = assertTimeline(value);
    renderTimeline(timeline.events);
    status.textContent = `Loaded ${timeline.events.length} redacted events · network-free`;
    status.dataset.ready = "true";
    requestAnimationFrame(render);
  })
  .catch((error) => {
    status.textContent = `Stage failed: ${error.message}`;
    status.dataset.ready = "false";
  });
