from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from rin_pet.timeline import (
    TimelineError,
    event_kind,
    parse_trace_bytes,
    state_for_kind,
    validate_timeline,
)


class TimelineTests(unittest.TestCase):
    def test_parser_keeps_structure_and_discards_free_form_values(self) -> None:
        raw = b"\n".join(
            [
                b'{"type":"user_message","timestamp":1000,"content":"PRIVATE_MESSAGE"}',
                b'{"type":"tool_call","timestamp":2000,'
                b'"arguments":{"path":"PRIVATE_PATH"}}',
                b'{"type":"approval_request","timestamp":4000,'
                b'"question":"PRIVATE_QUESTION"}',
                b'{"type":"task_complete","timestamp":6000,"result":"PRIVATE_RESULT"}',
            ]
        )
        timeline = parse_trace_bytes(raw)
        encoded = json.dumps(timeline)

        self.assertEqual(timeline["schemaVersion"], 1)
        self.assertEqual(timeline["source"]["recordCount"], 4)
        self.assertEqual(
            [event["state"] for event in timeline["events"]],
            ["idle", "running", "waiting", "jumping"],
        )
        for marker in (
            "PRIVATE_MESSAGE",
            "PRIVATE_PATH",
            "PRIVATE_QUESTION",
            "PRIVATE_RESULT",
        ):
            self.assertNotIn(marker, encoded)

    def test_nested_response_item_type_wins_over_envelope(self) -> None:
        record = {
            "type": "response_item",
            "payload": {"item": {"type": "function_call", "name": "private"}},
        }
        self.assertEqual(event_kind(record), "function_call")

    def test_unknown_type_becomes_activity_without_copying_name(self) -> None:
        timeline = parse_trace_bytes(b'{"type":"Private Secret Kind"}')
        self.assertEqual(timeline["events"][0]["kind"], "activity")
        self.assertNotIn("Private Secret Kind", json.dumps(timeline))

    def test_non_monotonic_and_missing_timestamps_become_monotonic(self) -> None:
        raw = (
            b'{"type":"tool_call","timestamp":3000}\n'
            b'{"type":"tool_result","timestamp":2000}\n'
            b'{"type":"final"}\n'
        )
        events = parse_trace_bytes(raw)["events"]
        offsets = [event["offsetMs"] for event in events]
        self.assertEqual(offsets, sorted(offsets))
        self.assertEqual(offsets[0], 0)

    def test_distant_identical_events_are_not_lost_by_coalescing(self) -> None:
        raw = (
            b'{"type":"tool_call","timestamp":0}\n'
            b'{"type":"tool_call","timestamp":20000}\n'
        )
        events = parse_trace_bytes(raw)["events"]
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1]["offsetMs"], 8_000)

    def test_large_timestamp_gaps_are_privacy_and_runtime_bounded(self) -> None:
        raw = (
            b'{"type":"user_message","timestamp":0}\n'
            b'{"type":"tool_call","timestamp":999999999999999}\n'
        )
        events = parse_trace_bytes(raw)["events"]
        self.assertEqual(events[1]["offsetMs"], 8_000)

    def test_alias_and_state_mapping(self) -> None:
        self.assertEqual(event_kind({"type": "needs_input"}), "request_user_input")
        self.assertEqual(state_for_kind("request_user_input"), "waiting")
        self.assertEqual(state_for_kind("failure"), "failed")
        self.assertEqual(state_for_kind("assistant_message"), "review")

    def test_bad_json_and_shape_fail_closed(self) -> None:
        with self.assertRaisesRegex(TimelineError, "line 1"):
            parse_trace_bytes(b"{nope}")
        with self.assertRaisesRegex(TimelineError, "JSON object"):
            parse_trace_bytes(b"[]")
        with self.assertRaisesRegex(TimelineError, "no JSON records"):
            parse_trace_bytes(b"\n")
        with self.assertRaisesRegex(TimelineError, "not UTF-8"):
            parse_trace_bytes(b"\xff")

    def test_record_limit_is_enforced(self) -> None:
        with patch("rin_pet.timeline.MAX_TRACE_RECORDS", 1):
            with self.assertRaisesRegex(TimelineError, "record safety limit"):
                parse_trace_bytes(b'{"type":"message"}\n{"type":"message"}')

    def test_timeline_validation_reports_all_core_errors(self) -> None:
        errors = validate_timeline(
            {
                "schemaVersion": 99,
                "events": [
                    {
                        "offsetMs": -1,
                        "durationMs": 1,
                        "state": "secret",
                        "kind": "private",
                    }
                ],
            }
        )
        self.assertEqual(len(errors), 5)
        self.assertIn("schemaVersion", errors[0])
        self.assertEqual(validate_timeline([]), ["timeline must be a JSON object"])


if __name__ == "__main__":
    unittest.main()
