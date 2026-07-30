from __future__ import annotations

import io
import unittest

from scripts.release_check import configure_utf8_output


class ReleaseCheckTests(unittest.TestCase):
    def test_legacy_windows_stream_is_reconfigured_for_unicode_json(self) -> None:
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="gbk", write_through=True)
        configure_utf8_output(stream)
        stream.write('{"status":"✔"}')
        stream.flush()
        self.assertEqual(raw.getvalue().decode("utf-8"), '{"status":"✔"}')

    def test_non_reconfigurable_capture_stream_is_supported(self) -> None:
        stream = io.StringIO()
        configure_utf8_output(stream)
        stream.write("ok")
        self.assertEqual(stream.getvalue(), "ok")


if __name__ == "__main__":
    unittest.main()
