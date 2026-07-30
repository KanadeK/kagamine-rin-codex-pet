from __future__ import annotations

PET_ID = "kagamine-rin"
SPRITE_VERSION = 2

CELL_WIDTH = 192
CELL_HEIGHT = 208
ATLAS_COLUMNS = 8
ATLAS_ROWS = 11
ATLAS_WIDTH = CELL_WIDTH * ATLAS_COLUMNS
ATLAS_HEIGHT = CELL_HEIGHT * ATLAS_ROWS
NEUTRAL_LOOK_FRAME = (0, 6)

STATE_ROWS = {
    "idle": 0,
    "running-right": 1,
    "running-left": 2,
    "waving": 3,
    "jumping": 4,
    "failed": 5,
    "waiting": 6,
    "running": 7,
    "review": 8,
    "look-row-9": 9,
    "look-row-10": 10,
}

FRAME_COUNTS = {
    "idle": 6,
    "running-right": 8,
    "running-left": 8,
    "waving": 4,
    "jumping": 5,
    "failed": 8,
    "waiting": 6,
    "running": 6,
    "review": 6,
    "look-row-9": 8,
    "look-row-10": 8,
}

FRAME_DURATIONS_MS = {
    "idle": (280, 110, 110, 140, 140, 320),
    "running-right": (120, 120, 120, 120, 120, 120, 120, 220),
    "running-left": (120, 120, 120, 120, 120, 120, 120, 220),
    "waving": (140, 140, 140, 280),
    "jumping": (140, 140, 140, 140, 280),
    "failed": (140, 140, 140, 140, 140, 140, 140, 240),
    "waiting": (150, 150, 150, 150, 150, 260),
    "running": (120, 120, 120, 120, 120, 220),
    "review": (150, 150, 150, 150, 150, 280),
}

LOOK_DIRECTIONS = (
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
)

TRACE_SCHEMA_VERSION = 1
MAX_TRACE_BYTES = 50 * 1024 * 1024
MAX_TRACE_RECORDS = 100_000
MIN_EVENT_DURATION_MS = 250
MAX_EVENT_DURATION_MS = 8_000
FIXED_ZIP_DATETIME = (2026, 1, 1, 0, 0, 0)
