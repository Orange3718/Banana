import unittest
from unittest import mock

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("telegram-natural-db-query.py")
spec = importlib.util.spec_from_file_location("telegram_natural_db_query", MODULE_PATH)
telegram_natural_db_query = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = telegram_natural_db_query
spec.loader.exec_module(telegram_natural_db_query)


class TelegramNaturalDbQueryTests(unittest.TestCase):
    def test_keyword_fallback_maps_failures(self):
        self.assertEqual(telegram_natural_db_query.fallback_key("최근 오류 원인 알려줘"), "failures")

    def test_keyword_fallback_maps_revenue(self):
        self.assertEqual(telegram_natural_db_query.fallback_key("수익 성과 어때"), "revenue")

    def test_unknown_defaults_to_status(self):
        self.assertEqual(telegram_natural_db_query.fallback_key("오늘 어때"), "status")

    @mock.patch.object(telegram_natural_db_query, "summarize")
    @mock.patch.object(telegram_natural_db_query, "classify")
    @mock.patch.object(telegram_natural_db_query, "db_exec")
    @mock.patch.object(telegram_natural_db_query, "db_scalar")
    def test_answer_uses_only_whitelisted_query(self, db_scalar, db_exec, classify, summarize):
        classify.return_value = {"query_key": "approvals", "reason": "test"}
        db_scalar.return_value = '[{"id": 7, "status": "pending"}]'
        summarize.return_value = {"reply": "승인 대기 1건입니다."}

        answer = telegram_natural_db_query.answer_question("승인 대기 있어?")

        self.assertEqual(answer.query_key, "approvals")
        self.assertEqual(answer.response_text, "승인 대기 1건입니다.")
        self.assertIn("v_atemoya_pending_approvals", db_scalar.call_args.args[0])
        db_exec.assert_called_once()


if __name__ == "__main__":
    unittest.main()
