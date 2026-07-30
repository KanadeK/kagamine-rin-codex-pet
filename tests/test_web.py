from __future__ import annotations

import unittest
from html.parser import HTMLParser

from tests.helpers import ROOT


class _DependencyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.dependencies: list[str] = []
        self.csp = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "script" and values.get("src"):
            self.dependencies.append(str(values["src"]))
        if tag == "link" and values.get("rel") == "stylesheet" and values.get("href"):
            self.dependencies.append(str(values["href"]))
        if tag == "meta" and values.get("http-equiv") == "Content-Security-Policy":
            self.csp = str(values.get("content", ""))


class WebTests(unittest.TestCase):
    def test_stage_has_only_local_runtime_dependencies_and_strict_csp(self) -> None:
        parser = _DependencyParser()
        parser.feed((ROOT / "web" / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(parser.dependencies, ["./styles.css", "./app.mjs"])
        self.assertIn("default-src 'self'", parser.csp)
        self.assertIn("connect-src 'self'", parser.csp)
        self.assertIn("object-src 'none'", parser.csp)

    def test_stage_uses_safe_dom_and_local_data_loading(self) -> None:
        app = (ROOT / "web" / "app.mjs").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", app)
        self.assertNotIn("eval(", app)
        self.assertIn('fetch("./timeline.json")', app)
        self.assertIn('image.src = "./pet/spritesheet.webp"', app)


if __name__ == "__main__":
    unittest.main()
