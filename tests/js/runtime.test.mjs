import assert from "node:assert/strict";
import test from "node:test";

import {
  assertTimeline,
  directionFrame,
  frameAt,
  timelineEventAt,
} from "../../web/runtime.mjs";

test("frameAt observes durations and reduced motion", () => {
  assert.deepEqual(frameAt("idle", 0), { row: 0, column: 0 });
  assert.deepEqual(frameAt("idle", 280), { row: 0, column: 1 });
  assert.deepEqual(frameAt("review", 9999, true), { row: 8, column: 0 });
  assert.throws(() => frameAt("private", 0), /Unsupported state/);
});

test("directionFrame maps all cardinal directions and deadzone", () => {
  assert.equal(directionFrame(0, 0), null);
  assert.deepEqual(directionFrame(0, -100), {
    row: 9,
    column: 0,
    direction: "000",
  });
  assert.equal(directionFrame(100, 0).direction, "090");
  assert.equal(directionFrame(0, 100).direction, "180");
  assert.equal(directionFrame(-100, 0).direction, "270");
});

test("timelineEventAt loops and selects the current structural event", () => {
  const events = [
    { offsetMs: 0, durationMs: 500, kind: "user_message", state: "idle" },
    { offsetMs: 500, durationMs: 500, kind: "tool_call", state: "running" },
  ];
  assert.equal(timelineEventAt(events, 100).kind, "user_message");
  assert.equal(timelineEventAt(events, 700).kind, "tool_call");
  assert.equal(timelineEventAt(events, 1100).kind, "user_message");
  assert.equal(timelineEventAt([], 0), null);
});

test("assertTimeline accepts allow-listed metadata and rejects unsafe shapes", () => {
  const valid = {
    schemaVersion: 1,
    events: [
      {
        offsetMs: 0,
        durationMs: 250,
        state: "running",
        kind: "tool_call",
      },
    ],
  };
  assert.equal(assertTimeline(valid), valid);
  assert.throws(
    () =>
      assertTimeline({
        schemaVersion: 1,
        events: [{ ...valid.events[0], kind: "private" }],
      }),
    /kind is unsupported/,
  );
  assert.throws(
    () =>
      assertTimeline({
        schemaVersion: 1,
        events: [{ ...valid.events[0], durationMs: 9000 }],
      }),
    /durationMs is invalid/,
  );
});
