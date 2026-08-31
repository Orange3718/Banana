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

    def test_revenue_autopilot_does_not_prompt_without_candidate(self):
        autopilot = workflow("AtemoyaRevenueAutopilot01.json")
        node_names = {node["name"] for node in autopilot["nodes"]}
        self.assertIn("처리 후보 있는가?", node_names)
        claim_route = autopilot["connections"]["후보 동기화와 1건 점유"]["main"][0][0]["node"]
        self.assertEqual(claim_route, "처리 후보 있는가?")
        true_route = autopilot["connections"]["처리 후보 있는가?"]["main"][0][0]["node"]
        false_route = autopilot["connections"]["처리 후보 있는가?"]["main"][1]
        self.assertEqual(true_route, "근거 제한 장문 프롬프트")
        self.assertEqual(false_route, [])

    def test_daily_trend_has_ollama_fallback_for_gemini_outage(self):
        trend = workflow("AtemoyaDailyTrend01.json")
        node_names = {node["name"] for node in trend["nodes"]}
        self.assertIn("Gemini 분석 성공인가?", node_names)
        self.assertIn("로컬 Qwen 트렌드 fallback", node_names)
        gemini = next(node for node in trend["nodes"] if node["name"] == "Gemini 트렌드 분석")
        self.assertEqual(gemini["parameters"]["url"], "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent")
        self.assertEqual(gemini["onError"], "continueRegularOutput")
        self.assertEqual(gemini["maxTries"], 3)
        self.assertEqual(gemini["waitBetweenTries"], 30000)
        success_route = trend["connections"]["Gemini 분석 성공인가?"]["main"][0][0]["node"]
        fallback_route = trend["connections"]["Gemini 분석 성공인가?"]["main"][1][0]["node"]
        self.assertEqual(success_route, "Gemini 결과 정리")
        self.assertEqual(fallback_route, "Ollama fallback 요청 준비")
        save_query_replacement = next(
            node["parameters"]["options"]["queryReplacement"]
            for node in trend["nodes"]
            if node["name"] == "트렌드 보고서 저장"
        )
        self.assertIn("$json.report_text", save_query_replacement)

    def test_telegram_has_natural_language_local_llm_router(self):
        memory = workflow("AtemoyaTelegramMemory01.json")
        node_names = {node["name"] for node in memory["nodes"]}
        self.assertIn("자연어 운영 문맥 조회", node_names)
        self.assertIn("로컬 Qwen 자연어 대화", node_names)
        self.assertIn("자연어 의도 안전 검증", node_names)
        self.assertIn("자연어 결정인가?", node_names)
        natural_route = memory["connections"]["AI 질문인가?"]["main"][1][0]["node"]
        self.assertEqual(natural_route, "자연어 운영 문맥 조회")
        llm = next(node for node in memory["nodes"] if node["name"] == "로컬 Qwen 자연어 대화")
        self.assertEqual(llm["parameters"]["url"], "http://host.docker.internal:11434/api/chat")
        validate_code = next(node["parameters"]["jsCode"] for node in memory["nodes"] if node["name"] == "자연어 의도 안전 검증")
        self.assertIn("pending_count", validate_code)
        self.assertIn("should_decide", validate_code)


if __name__ == "__main__":
    unittest.main()
