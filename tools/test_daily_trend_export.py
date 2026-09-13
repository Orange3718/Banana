import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "n8n/workflows/exports/AtemoyaDailyTrend01.json"


def has_literal_newline_in_single_quote(source: str) -> bool:
    quoted = False
    escaped = False
    for ch in source:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == "'":
            quoted = not quoted
        elif ch in "\r\n" and quoted:
            return True
    return False


class DailyTrendExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads(EXPORT.read_text(encoding="utf-8"))
        cls.nodes = {node["name"]: node for node in payload[0]["nodes"]}

    def test_fallback_has_no_literal_newline_in_single_quoted_js(self):
        code = self.nodes["Ollama fallback 요청 준비"]["parameters"]["jsCode"]
        self.assertFalse(has_literal_newline_in_single_quote(code))

    def test_gemini_output_budget_is_bounded(self):
        body = self.nodes["Gemini 트렌드 분석"]["parameters"]["body"]
        self.assertIn("maxOutputTokens: 1400", body)
        self.assertNotIn("maxOutputTokens: 4096", body)

    def test_fallback_model_and_budget_are_explicit(self):
        code = self.nodes["Ollama fallback 요청 준비"]["parameters"]["jsCode"]
        self.assertIn("qwen3.5:4b", code)
        self.assertIn("num_predict:900", code)


if __name__ == "__main__":
    unittest.main()
