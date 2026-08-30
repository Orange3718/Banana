#!/usr/bin/env python3
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("runner", Path(__file__).with_name("local-llm-runner.py"))
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class TopicSelectionTests(unittest.TestCase):
    def test_generic_hackernews_topic_is_not_revenue_work(self):
        rows = [
            {"title": "Python compiler internals", "score": 10},
            {"title": "Creator commerce product comparison", "score": 38},
        ]
        self.assertEqual(runner.revenue_candidates(rows), [rows[1]])

    def test_productivity_does_not_match_product(self):
        rows = [{"title": "Good Culture Is the Biggest Productivity Hack, Not AI", "score": 60}]
        self.assertEqual(runner.revenue_candidates(rows), [])

    def test_recent_topics_are_not_reused(self):
        rows = [
            {"topic_key": "old", "title": "AI shopping report", "url": "https://example.com/old", "channel": "google-news", "score": 50},
            {"topic_key": "new", "title": "Creator commerce tool", "url": "https://example.com/new", "channel": "reddit", "score": 30},
        ]
        jobs = runner.plan_jobs(rows, {"old"})
        self.assertEqual([job["topic_key"] for job in jobs], ["new"])

    def test_two_different_evidence_items_feed_two_lanes(self):
        rows = [
            {"topic_key": "a", "title": "AI shopping", "url": "https://example.com/a", "channel": "google-news", "score": 50},
            {"topic_key": "b", "title": "Commerce payments", "url": "https://example.com/b", "channel": "hackernews", "score": 20},
        ]
        jobs = runner.plan_jobs(rows, set())
        self.assertEqual(len(jobs), 2)
        self.assertNotEqual(jobs[0]["topic_key"], jobs[1]["topic_key"])
        self.assertIn(rows[0]["url"], jobs[0]["prompt"])
        self.assertIn(rows[1]["url"], jobs[1]["prompt"])

    def test_republished_story_is_selected_only_once(self):
        rows = [
            {"topic_key": "a", "title": "SHIP.com Introduces AI Shipping Manager and Agentic Commerce Tools for Online Sellers - PR Newswire", "url": "https://example.com/a", "channel": "google-news", "score": 50},
            {"topic_key": "b", "title": "Ship.com launches AI shipping tools for online sellers - Mass Market Retailers", "url": "https://example.com/b", "channel": "google-news", "score": 49},
            {"topic_key": "c", "title": "Creators compare affiliate conversion costs", "url": "https://example.com/c", "channel": "reddit", "score": 20},
        ]
        jobs = runner.plan_jobs(rows, set())
        self.assertEqual([job["topic_key"] for job in jobs], ["a", "c"])

    def test_recent_similar_title_is_in_cooldown_even_with_new_url(self):
        rows = [{"topic_key": "new-url", "title": "Ship.com launches AI shipping tools for online sellers", "url": "https://example.com/new", "channel": "google-news", "score": 50}]
        jobs = runner.plan_jobs(rows, set(), ["SHIP.com Introduces AI Shipping Manager and Agentic Commerce Tools for Online Sellers"])
        self.assertEqual(jobs, [])

    def test_second_lane_prefers_another_channel(self):
        rows = [
            {"topic_key": "a", "title": "AI shoppers change product discovery", "url": "https://example.com/a", "channel": "google-news", "score": 60},
            {"topic_key": "b", "title": "Visa agentic payment platform", "url": "https://example.com/b", "channel": "google-news", "score": 55},
            {"topic_key": "c", "title": "Open source local model benchmark", "url": "https://example.com/c", "channel": "hackernews", "score": 20},
        ]
        jobs = runner.plan_jobs(rows, set())
        self.assertEqual(
            [job["channel"] for job in jobs],
            ["google-news", "hackernews"],
        )


if __name__ == "__main__":
    unittest.main()
