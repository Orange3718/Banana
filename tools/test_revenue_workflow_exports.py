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

    def test_one_telegram_router_handles_approvals_and_local_reviews(self):
        memory = workflow("AtemoyaTelegramMemory01.json")
        review = workflow("AtemoyaLocalLLMReviewGate01.json")
        self.assertTrue(memory["active"])
        self.assertFalse(review["active"])
        node_names = {node["name"] for node in memory["nodes"]}
        self.assertIn("승인 명령 해석", node_names)
        self.assertIn("GOOD BAD 수정 해석", node_names)
        self.assertIn("로컬 검토 명령인가?", node_names)
        false_route = memory["connections"]["사업 승인 명령인가?"]["main"][1][0]["node"]
        self.assertEqual(false_route, "로컬 검토 명령인가?")
        approval_query = next(
            node["parameters"]["query"] for node in memory["nodes"] if node["name"] == "승인 상태 저장"
        )
        self.assertIn("이미 승인 완료", approval_query)


if __name__ == "__main__":
    unittest.main()
