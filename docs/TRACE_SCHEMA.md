# RinTrace privacy contract

RinTrace converts newline-delimited Codex activity records into a deliberately
small animation timeline. It is a structural parser, not a transcript
exporter.

## Input boundary

The parser accepts UTF-8 JSONL up to 50 MiB and 100,000 non-empty records.
Every line must contain a JSON object. It recognizes only allow-listed values
from nested `type` fields and timestamps from `timestamp`, `created_at`, or
`time`.

The parser never copies arbitrary keys or values. Unknown `type` values become
the generic `activity` kind rather than being preserved.

## Output schema

```json
{
  "schemaVersion": 1,
  "redaction": {
    "mode": "metadata-only",
    "discarded": ["message text", "prompt text", "tool arguments"]
  },
  "source": {
    "sha256": "hex digest of the complete input",
    "recordCount": 10,
    "byteCount": 1234
  },
  "events": [
    {
      "offsetMs": 0,
      "durationMs": 1000,
      "state": "running",
      "kind": "turn_context",
      "sourceLine": 1
    }
  ]
}
```

`offsetMs` is relative to the first usable timestamp; the original absolute
time is never emitted. Missing or non-monotonic timestamps are repaired into a
monotonic sequence. Individual timestamp gaps and durations are bounded to
8,000 ms (durations have a 250 ms minimum), preventing a malformed timestamp
from creating an impractically long browser timeline.

## State mapping

| Structural event | Pet state |
| --- | --- |
| `user_message` | `idle` |
| `approval_request`, `request_user_input` | `waiting` |
| `assistant_message`, `review` | `review` |
| `error`, `failure`, `cancelled` | `failed` |
| `assistant_final`, `final`, `task_complete`, `turn_complete` | `jumping` |
| all other allow-listed kinds | `running` |

The mapping is intentionally coarse. It communicates lifecycle state without
exposing what the user said or what a tool did.

## Discarded data

RinTrace discards message bodies, prompts, reasoning summaries, tool names,
arguments, results, file paths, account identifiers, environment values, error
messages, final answers, and every unrecognized value.

The input SHA-256 is retained so an operator can prove which local file was
processed without publishing that file. A digest is not encryption: do not
publish the original log or use the digest as an access control mechanism.

## Test fixture

`examples/sanitized-session.jsonl` contains conspicuous `PRIVATE_*` values.
`examples/sanitized-timeline.json` is the expected output and must contain none
of them. The release gate regenerates the timeline byte-for-byte and fails if
the golden file is stale or any parser behavior changes unexpectedly.
