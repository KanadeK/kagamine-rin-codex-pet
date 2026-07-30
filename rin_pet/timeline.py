from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from .constants import (
    MAX_EVENT_DURATION_MS,
    MAX_TRACE_BYTES,
    MAX_TRACE_RECORDS,
    MIN_EVENT_DURATION_MS,
    TRACE_SCHEMA_VERSION,
)
from .safeio import atomic_write_json


class TimelineError(ValueError):
    """A trace is malformed or exceeds a privacy/safety limit."""


_SAFE_KIND = re.compile(r"[^a-z0-9_.-]+")
_KNOWN_KINDS = {
    "activity",
    "approval_request",
    "assistant_final",
    "assistant_message",
    "cancelled",
    "custom_tool_call",
    "custom_tool_call_output",
    "error",
    "event_msg",
    "failure",
    "final",
    "function_call",
    "function_call_output",
    "message",
    "reasoning",
    "request_user_input",
    "response_item",
    "review",
    "task_complete",
    "task_started",
    "tool_call",
    "tool_result",
    "turn_complete",
    "turn_context",
    "user_message",
}

_WAITING_KINDS = {"approval_request", "request_user_input"}
_FAILED_KINDS = {"error", "failure", "cancelled"}
_READY_KINDS = {"assistant_final", "final", "task_complete", "turn_complete"}
_REVIEW_KINDS = {"assistant_message", "review"}
_IDLE_KINDS = {"user_message"}

_DEFAULT_DURATIONS = {
    "idle": 900,
    "running": 1_000,
    "waiting": 1_500,
    "review": 1_100,
    "jumping": 1_300,
    "failed": 1_600,
}


def _normalize_kind(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = _SAFE_KIND.sub("_", value.strip().lower()).strip("_.-")
    if normalized in _KNOWN_KINDS:
        return normalized
    aliases = {
        "completed": "task_complete",
        "complete": "task_complete",
        "needs_input": "request_user_input",
        "approval": "approval_request",
        "tool": "tool_call",
        "tool_output": "tool_result",
        "failed": "failure",
        "canceled": "cancelled",
    }
    return aliases.get(normalized)


def _candidate_objects(record: dict[str, Any]) -> Iterable[dict[str, Any]]:
    payload = record.get("payload")
    item = record.get("item")
    event = record.get("event")
    if isinstance(payload, dict):
        payload_item = payload.get("item")
        payload_event = payload.get("event")
        if isinstance(payload_item, dict):
            yield payload_item
        if isinstance(payload_event, dict):
            yield payload_event
    if isinstance(item, dict):
        yield item
    if isinstance(event, dict):
        yield event
    if isinstance(payload, dict):
        yield payload
    yield record


def event_kind(record: dict[str, Any]) -> str:
    for candidate in _candidate_objects(record):
        kind = _normalize_kind(candidate.get("type"))
        if kind and kind not in {"event_msg", "response_item"}:
            return kind
    for candidate in _candidate_objects(record):
        kind = _normalize_kind(candidate.get("type"))
        if kind:
            return kind
    return "activity"


def state_for_kind(kind: str) -> str:
    if kind in _WAITING_KINDS:
        return "waiting"
    if kind in _FAILED_KINDS:
        return "failed"
    if kind in _READY_KINDS:
        return "jumping"
    if kind in _REVIEW_KINDS:
        return "review"
    if kind in _IDLE_KINDS:
        return "idle"
    return "running"


def _parse_timestamp(value: Any) -> int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if number > 10_000_000_000:
            return int(number)
        if number > 1_000_000_000:
            return int(number * 1_000)
        if number >= 0:
            return int(number)
    if isinstance(value, str):
        text = value.strip()
        if not text or len(text) > 40:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        return int(parsed.timestamp() * 1_000)
    return None


def _record_timestamp(record: dict[str, Any]) -> int | None:
    for candidate in _candidate_objects(record):
        for key in ("timestamp", "created_at", "time"):
            parsed = _parse_timestamp(candidate.get(key))
            if parsed is not None:
                return parsed
    return None


def _bounded_duration(value: int, state: str) -> int:
    if value <= 0:
        value = _DEFAULT_DURATIONS[state]
    return max(MIN_EVENT_DURATION_MS, min(MAX_EVENT_DURATION_MS, value))


def parse_trace_bytes(data: bytes) -> dict[str, Any]:
    if len(data) > MAX_TRACE_BYTES:
        raise TimelineError(
            f"trace exceeds {MAX_TRACE_BYTES} byte safety limit: {len(data)}"
        )
    digest = hashlib.sha256(data).hexdigest()
    records: list[tuple[int, int | None, str, str]] = []
    for line_number, raw_line in enumerate(data.splitlines(), start=1):
        if not raw_line.strip():
            continue
        if len(records) >= MAX_TRACE_RECORDS:
            raise TimelineError(
                f"trace exceeds {MAX_TRACE_RECORDS} record safety limit"
            )
        try:
            decoded = raw_line.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise TimelineError(f"line {line_number} is not UTF-8: {exc}") from exc
        try:
            value = json.loads(decoded)
        except json.JSONDecodeError as exc:
            raise TimelineError(
                f"line {line_number} is not valid JSON: {exc.msg}"
            ) from exc
        if not isinstance(value, dict):
            raise TimelineError(f"line {line_number} must contain a JSON object")
        kind = event_kind(value)
        records.append(
            (line_number, _record_timestamp(value), kind, state_for_kind(kind))
        )

    if not records:
        raise TimelineError("trace contains no JSON records")

    absolute: list[int] = []
    last: int | None = None
    for index, (_, timestamp, _, _) in enumerate(records):
        if timestamp is None:
            timestamp = (last + 1_000) if last is not None else index * 1_000
        if last is not None and timestamp <= last:
            timestamp = last + 1
        if last is not None and timestamp - last > MAX_EVENT_DURATION_MS:
            timestamp = last + MAX_EVENT_DURATION_MS
        absolute.append(timestamp)
        last = timestamp
    origin = absolute[0]

    events: list[dict[str, Any]] = []
    for index, (line_number, _, kind, state) in enumerate(records):
        offset = absolute[index] - origin
        if index + 1 < len(records):
            raw_duration = absolute[index + 1] - absolute[index]
        else:
            raw_duration = _DEFAULT_DURATIONS[state]
        duration = _bounded_duration(raw_duration, state)
        event = {
            "offsetMs": offset,
            "durationMs": duration,
            "state": state,
            "kind": kind,
            "sourceLine": line_number,
        }
        if (
            events
            and events[-1]["state"] == state
            and events[-1]["kind"] == kind
            and offset <= events[-1]["offsetMs"] + events[-1]["durationMs"]
        ):
            previous = events[-1]
            previous_end = max(
                previous["offsetMs"] + previous["durationMs"],
                offset + duration,
            )
            merged_duration = previous_end - previous["offsetMs"]
            if merged_duration <= MAX_EVENT_DURATION_MS:
                previous["durationMs"] = merged_duration
                continue
        events.append(event)

    return {
        "schemaVersion": TRACE_SCHEMA_VERSION,
        "redaction": {
            "mode": "metadata-only",
            "discarded": [
                "message text",
                "prompt text",
                "tool arguments",
                "tool output",
                "file paths",
                "account data",
            ],
        },
        "source": {
            "sha256": digest,
            "recordCount": len(records),
            "byteCount": len(data),
        },
        "events": events,
    }


def parse_trace_file(source: Path, output: Path | None = None) -> dict[str, Any]:
    data = source.read_bytes()
    timeline = parse_trace_bytes(data)
    if output is not None:
        atomic_write_json(output, timeline)
    return timeline


def validate_timeline(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["timeline must be a JSON object"]
    if value.get("schemaVersion") != TRACE_SCHEMA_VERSION:
        errors.append(f"schemaVersion must be {TRACE_SCHEMA_VERSION}")
    events = value.get("events")
    if not isinstance(events, list) or not events:
        errors.append("events must be a non-empty array")
        return errors
    previous = -1
    valid_states = set(_DEFAULT_DURATIONS)
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append(f"events[{index}] must be an object")
            continue
        offset = event.get("offsetMs")
        duration = event.get("durationMs")
        state = event.get("state")
        kind = event.get("kind")
        if not isinstance(offset, int) or offset < 0 or offset < previous:
            errors.append(
                f"events[{index}].offsetMs must be a non-negative monotonic integer"
            )
        else:
            previous = offset
        if (
            not isinstance(duration, int)
            or duration < MIN_EVENT_DURATION_MS
            or duration > MAX_EVENT_DURATION_MS
        ):
            errors.append(f"events[{index}].durationMs is outside safety bounds")
        if state not in valid_states:
            errors.append(f"events[{index}].state is unsupported: {state!r}")
        if kind not in _KNOWN_KINDS:
            errors.append(f"events[{index}].kind is not allow-listed: {kind!r}")
    return errors
