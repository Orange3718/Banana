#!/usr/bin/env python3
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def workflow(name):
    data = json.loads((ROOT / "n8n/workflows/exports" / name).read_text(encoding="utf-8"))
    return data[0] if isinstance(data, list) else data


class RevenueWorkflowExportTests(unittest.TestCase):
    def test_guardian_never_calls_zero_publication_good(self):
        guardian = workflow("AtemoyaOpsGuardian01.json")
        query = next(node["parameters"]["query"] for node in guardian["nodes"] if node["name"] == "운영 지표 조회")
        self.assertIn("OR published_7d=0 OR", query)
        self.assertNotIn("autopilot_actionable>0 AND published_7d=0", query)

    def test_autopilot_requires_revenue_candidate_task(self):
        autopilot = workflow("AtemoyaRevenueAutopilot01.json")
        query = next(node["parameters"]["query"] for node in autopilot["nodes"] if node["name"] == "후보 동기화와 1건 점유")
        self.assertIn("r.task_name='신규 수익 콘텐츠 후보'", query)
        self.assertIn("approval_requests", query)
        self.assertIn("lower(COALESCE(r.metadata->>'topic_title','')) ~", query)
        self.assertNotIn("topic_title','')||' '||COALESCE(r.result_summary", query)
        qa_code = next(node["parameters"]["jsCode"] for node in autopilot["nodes"] if node["name"] == "자동 QA와 안전 정리")
        self.assertIn("replace(/무조건적으로?/g,'자동으로')", qa_code)
        self.assertIn("unsupportedNumbers", qa_code)


if __name__ == "__main__":
    unittest.main()
