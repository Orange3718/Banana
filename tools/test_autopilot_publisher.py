#!/usr/bin/env python3
import importlib.util
import sys
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("publisher", Path(__file__).with_name("autopilot-publisher.py"))
publisher = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = publisher
SPEC.loader.exec_module(publisher)


class PublisherTests(unittest.TestCase):
    def test_slug_is_safe_and_bounded(self):
        slug = publisher.safe_slug("AI 쇼핑: Price & Review 2026")
        self.assertEqual(slug, "ai-price-review-2026")
        self.assertLessEqual(len(slug), 72)

    def test_dangerous_html_is_removed(self):
        body = '<h2>정상</h2><script>alert(1)</script><p onclick="x()">본문</p><a href="javascript:bad">링크</a>'
        clean = publisher.sanitize_body(body)
        self.assertNotIn("script", clean.lower())
        self.assertNotIn("onclick", clean.lower())
        self.assertNotIn("javascript:", clean.lower())

    def test_render_requires_substantial_body(self):
        row = {"title": "테스트", "job_key": "test", "source_url": "https://example.com", "content_metadata": {"body_html": "<p>짧음</p>"}}
        with self.assertRaises(ValueError):
            publisher.render_page(row)


if __name__ == "__main__":
    unittest.main()
