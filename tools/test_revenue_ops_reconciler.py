#!/usr/bin/env python3
import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("reconciler", Path(__file__).with_name("revenue-ops-reconciler.py"))
reconciler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reconciler)


class RevenueOpsAssessmentTests(unittest.TestCase):
    def test_review_when_no_candidates_and_no_publication(self):
        status, _ = reconciler.assess({"queued": 0, "retry": 0, "oldest_actionable_minutes": 0, "pending_approval_minutes": 0, "published_7d": 0})
        self.assertEqual(status, "review")

    def test_good_when_pipeline_is_fresh(self):
        status, _ = reconciler.assess({"queued": 0, "retry": 0, "oldest_actionable_minutes": 30, "pending_approval_minutes": 0, "published_7d": 1})
        self.assertEqual(status, "good")

    def test_review_when_candidates_have_no_publication(self):
        status, _ = reconciler.assess({"queued": 3, "retry": 0, "oldest_actionable_minutes": 60, "pending_approval_minutes": 0, "published_7d": 0})
        self.assertEqual(status, "review")

    def test_bad_after_seventy_two_hours(self):
        status, _ = reconciler.assess({"queued": 1, "retry": 0, "oldest_actionable_minutes": 4320, "pending_approval_minutes": 0, "published_7d": 0})
        self.assertEqual(status, "bad")


if __name__ == "__main__":
    unittest.main()
