import unittest

from inspect_ga4_report import inspect_report


PREAMBLE = "# 계정: Atemoya\n# 속성: Atemoya\n# 시작일: 20261004\n# 종료일: 20261031\n"
PAGES = "페이지 경로 및 화면 클래스,조회수,활성 사용자,활성 사용자당 조회수,활성 사용자당 평균 참여 시간,이벤트 수,주요 이벤트,총수익\n"
EVENTS = "이벤트 이름,이벤트 수,총 사용자,활성 사용자당 이벤트 수,총수익\n"


def inspect(text):
    return inspect_report(text.encode(), "551097737", "G-LKX74KWHLM")


class GA4ReportTests(unittest.TestCase):
    def test_page_period_aggregate_is_not_daily_or_revenue(self):
        result = inspect(PREAMBLE + PAGES + "/Banana/guides/a.html,1,1,1,19,6,0,0\n/Banana/offers/b.html,2,1,2,20,7,0,0\n")
        self.assertEqual((result["page_views"], result["affiliate_page_views"]), (3, 2))
        self.assertFalse(result["daily_metric_eligible"])
        self.assertFalse(result["financial_posting"])

    def test_absent_affiliate_click_stays_absent(self):
        result = inspect(PREAMBLE + EVENTS + "page_view,2,2,1,0\n")
        self.assertFalse(result["affiliate_click_listed"])
        self.assertIsNone(result["affiliate_click_reported"])

    def test_reported_affiliate_click_has_count(self):
        result = inspect(PREAMBLE + EVENTS + "affiliate_click,0,0,0,0\n")
        self.assertTrue(result["affiliate_click_listed"])
        self.assertEqual(result["affiliate_click_reported"], 0)

    def test_wrong_property_or_unknown_columns_rejected(self):
        with self.assertRaises(ValueError):
            inspect(PREAMBLE.replace("Atemoya", "Feijoa") + EVENTS)
        with self.assertRaises(ValueError):
            inspect(PREAMBLE + "event,events\npage_view,1\n")

    def test_duplicate_and_negative_counts_rejected(self):
        with self.assertRaises(ValueError):
            inspect(PREAMBLE + EVENTS + "page_view,2,2,1,0\npage_view,3,3,1,0\n")
        with self.assertRaises(ValueError):
            inspect(PREAMBLE + EVENTS + "page_view,-1,1,1,0\n")

    def test_empty_export_is_not_observed_zero(self):
        result = inspect(PREAMBLE + EVENTS)
        self.assertEqual(result["state"], "empty_report")
        self.assertIsNone(result["affiliate_click_reported"])


if __name__ == "__main__":
    unittest.main()
