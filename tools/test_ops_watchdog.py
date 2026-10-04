#!/usr/bin/env python3
import importlib.util
import datetime as dt
import json
import sqlite3
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

    def test_dns_failure_is_bad(self):
        with patch.object(watchdog.socket, "getaddrinfo", side_effect=OSError("resolver unavailable")):
            check = watchdog.dns_check()
        self.assertEqual(check.status, "bad")
        self.assertEqual(len(check.details["failures"]), len(watchdog.DNS_HOSTS))

    def test_trading_collector_freshness(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "neural.db"
            with sqlite3.connect(path) as conn:
                conn.execute("CREATE TABLE collector_health(account TEXT PRIMARY KEY,time TEXT,status TEXT)")
                conn.executemany(
                    "INSERT INTO collector_health VALUES(?,?,?)",
                    [
                        ("upbit", "2026-09-27T06:00:00+00:00", "connected"),
                        ("binance_futures", "2026-09-27T05:50:00+00:00", "connected"),
                    ],
                )
            now = dt.datetime(2026, 9, 27, 6, 1, tzinfo=dt.timezone.utc)
            with patch.object(watchdog, "TRADING_DB", path):
                checks = watchdog.trading_collector_checks(now=now)
        statuses = {check.code: check.status for check in checks}
        self.assertEqual(statuses["collector:upbit"], "good")
        self.assertEqual(statuses["collector:binance_futures"], "bad")

    def test_revenue_pipeline_is_review_when_nothing_published(self):
        check = watchdog.revenue_pipeline_check({"queued": 4, "retry": 0, "awaiting_approval": 0, "approved": 0, "branch_ready": 0, "published_7d": 0, "oldest_minutes": 60})
        self.assertEqual(check.status, "review")

    def test_revenue_pipeline_is_bad_when_stalled_three_days(self):
        check = watchdog.revenue_pipeline_check({"queued": 4, "retry": 0, "awaiting_approval": 0, "approved": 0, "branch_ready": 0, "published_7d": 0, "oldest_minutes": 4320})
        self.assertEqual(check.status, "bad")

    def test_revenue_pipeline_is_good_after_publication(self):
        check = watchdog.revenue_pipeline_check({"queued": 2, "retry": 0, "awaiting_approval": 0, "approved": 0, "branch_ready": 0, "published_7d": 1, "oldest_minutes": 120})
        self.assertEqual(check.status, "good")

    def test_direct_publication_is_good_while_future_work_is_scheduled(self):
        check = watchdog.direct_publication_check({"total": 10, "queued": 9, "running": 0, "retry_wait": 0, "manual_review": 0, "failed": 0, "published": 1, "due": 0, "oldest_due_minutes": 0})
        self.assertEqual(check.status, "good")

    def test_direct_publication_is_bad_after_due_item_stalls(self):
        check = watchdog.direct_publication_check({"total": 10, "queued": 9, "running": 0, "retry_wait": 0, "manual_review": 0, "failed": 0, "published": 1, "due": 1, "oldest_due_minutes": 46})
        self.assertEqual(check.status, "bad")

    def test_direct_publication_stops_on_manual_review(self):
        check = watchdog.direct_publication_check({"total": 10, "queued": 8, "running": 0, "retry_wait": 0, "manual_review": 1, "failed": 0, "published": 1, "due": 0, "oldest_due_minutes": 0})
        self.assertEqual(check.status, "bad")


if __name__ == "__main__":
    unittest.main()
