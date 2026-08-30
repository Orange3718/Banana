#!/usr/bin/env python3
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("watchdog", Path(__file__).with_name("ops-watchdog.py"))
watchdog = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = watchdog
SPEC.loader.exec_module(watchdog)


class WatchdogTests(unittest.TestCase):
    def test_fingerprint_does_not_depend_on_message(self):
        first = watchdog.Check("n8n", "healthz", "bad", "timeout")
        second = watchdog.Check("n8n", "healthz", "bad", "connection refused")
        self.assertEqual(first.fingerprint, second.fingerprint)

    def test_source_freshness_good(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.json"
            path.write_text(json.dumps({"sources": [{"items": [{"title": "a"}]}, {"items": [{"title": "b"}]}]}))
            with patch.object(watchdog, "SOURCE_FILE", path):
                check = watchdog.source_check(now=path.stat().st_mtime + 60)
        self.assertEqual(check.status, "good")

    def test_source_freshness_bad_after_three_hours(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.json"
            path.write_text(json.dumps({"sources": [{"items": [{"title": "a"}]}]}))
            with patch.object(watchdog, "SOURCE_FILE", path):
                check = watchdog.source_check(now=path.stat().st_mtime + 10801)
        self.assertEqual(check.status, "bad")

    def test_remediation_has_one_hour_cooldown(self):
        state = {"last_remediation": {"n8n|healthz": 1000}}
        self.assertFalse(watchdog.may_remediate(state, "n8n|healthz", now=2000))
        self.assertTrue(watchdog.may_remediate(state, "n8n|healthz", now=5000))

    def test_memory_pressure_uses_current_free_percentage(self):
        completed = type("Result", (), {"returncode": 0, "stdout": "System-wide memory free percentage: 63%", "stderr": ""})()
        with patch.object(watchdog, "command", return_value=completed):
            check = watchdog.memory_pressure_check()
        self.assertEqual(check.status, "good")
        self.assertEqual(check.details["free_percent"], 63)

    def test_revenue_pipeline_is_review_when_nothing_published(self):
        check = watchdog.revenue_pipeline_check({"queued": 4, "retry": 0, "awaiting_approval": 0, "approved": 0, "branch_ready": 0, "published_7d": 0, "oldest_minutes": 60})
        self.assertEqual(check.status, "review")

    def test_revenue_pipeline_is_bad_when_stalled_three_days(self):
        check = watchdog.revenue_pipeline_check({"queued": 4, "retry": 0, "awaiting_approval": 0, "approved": 0, "branch_ready": 0, "published_7d": 0, "oldest_minutes": 4320})
        self.assertEqual(check.status, "bad")

    def test_revenue_pipeline_is_good_after_publication(self):
        check = watchdog.revenue_pipeline_check({"queued": 2, "retry": 0, "awaiting_approval": 0, "approved": 0, "branch_ready": 0, "published_7d": 1, "oldest_minutes": 120})
        self.assertEqual(check.status, "good")


if __name__ == "__main__":
    unittest.main()
