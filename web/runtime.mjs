export const CELL_WIDTH = 192;
export const CELL_HEIGHT = 208;

export const STATE_ROWS = Object.freeze({
  idle: 0,
  "running-right": 1,
  "running-left": 2,
  waving: 3,
  jumping: 4,
  failed: 5,
  waiting: 6,
  running: 7,
  review: 8,
});

export const FRAME_DURATIONS = Object.freeze({
  idle: [280, 110, 110, 140, 140, 320],
  "running-right": [120, 120, 120, 120, 120, 120, 120, 220],
  "running-left": [120, 120, 120, 120, 120, 120, 120, 220],
  waving: [140, 140, 140, 280],
  jumping: [140, 140, 140, 140, 280],
  failed: [140, 140, 140, 140, 140, 140, 140, 240],
  waiting: [150, 150, 150, 150, 150, 260],
  running: [120, 120, 120, 120, 120, 220],
  review: [150, 150, 150, 150, 150, 280],
});

export const LOOK_DIRECTIONS = Object.freeze([
  "000",
  "022.5",
  "045",
  "067.5",
  "090",
  "112.5",
  "135",
  "157.5",
  "180",
  "202.5",
  "225",
  "247.5",
  "270",
  "292.5",
  "315",
  "337.5",
]);

export const TIMELINE_KINDS = Object.freeze(
  new Set([
    "activity",
    "approval_request",
    "assistant_final",
    "assistant_message",
    "cancelled",
    "custom_tool_call",
    "custom_tool_call_output",
    "error",
    "failure",
    "final",
    "function_call",
    "function_call_output",
    "message",
    "reasoning",
    "request_user_input",
    "review",
    "task_complete",
    "task_started",
    "tool_call",
    "tool_result",
    "turn_complete",
    "turn_context",
    "user_message",
  ]),
);

export function frameAt(state, elapsedMs, reducedMotion = false) {
  const durations = FRAME_DURATIONS[state];
  if (!durations) {
    throw new Error(`Unsupported state: ${state}`);
  }
  if (reducedMotion) return { row: STATE_ROWS[state], column: 0 };
  const cycle = durations.reduce((total, value) => total + value, 0);
  let cursor = ((elapsedMs % cycle) + cycle) % cycle;
  for (let column = 0; column < durations.length; column += 1) {
    if (cursor < durations[column]) {
      return { row: STATE_ROWS[state], column };
    }
    cursor -= durations[column];
  }
  return { row: STATE_ROWS[state], column: durations.length - 1 };
}

export function directionFrame(dx, dy, deadzone = 24) {
  if (Math.hypot(dx, dy) < deadzone) return null;
  const degrees = (Math.atan2(dx, -dy) * 180) / Math.PI;
  const normalized = (degrees + 360) % 360;
  const index = Math.round(normalized / 22.5) % 16;
  return {
    row: index < 8 ? 9 : 10,
    column: index < 8 ? index : index - 8,
    direction: LOOK_DIRECTIONS[index],
  };
}

export function timelineEventAt(events, elapsedMs) {
  if (!Array.isArray(events) || events.length === 0) return null;
  const end = Math.max(
    ...events.map((event) => event.offsetMs + event.durationMs),
  );
  const cursor = end > 0 ? ((elapsedMs % end) + end) % end : 0;
  let selected = events[0];
  for (const event of events) {
    if (event.offsetMs <= cursor) selected = event;
    else break;
  }
  return selected;
}

export function assertTimeline(value) {
  if (
    !value ||
    value.schemaVersion !== 1 ||
    !Array.isArray(value.events) ||
    value.events.length === 0
  ) {
    throw new Error("Timeline schema is not supported");
  }
  const states = new Set([
    "idle",
    "running",
    "waiting",
    "review",
    "jumping",
    "failed",
  ]);
  let previous = -1;
  for (const [index, event] of value.events.entries()) {
    if (
      !Number.isInteger(event.offsetMs) ||
      event.offsetMs < 0 ||
      event.offsetMs < previous
    ) {
      throw new Error(`events[${index}].offsetMs is not monotonic`);
    }
    if (
      !Number.isInteger(event.durationMs) ||
      event.durationMs < 250 ||
      event.durationMs > 8000
    ) {
      throw new Error(`events[${index}].durationMs is invalid`);
    }
    if (!states.has(event.state)) {
      throw new Error(`events[${index}].state is unsupported`);
    }
    if (!TIMELINE_KINDS.has(event.kind)) {
      throw new Error(`events[${index}].kind is unsupported`);
    }
    previous = event.offsetMs;
  }
  return value;
}
