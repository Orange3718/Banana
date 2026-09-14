#!/usr/bin/env python3
import copy
import unittest
from unittest import mock

import affiliate_direct_publisher as publisher
import seed_affiliate_publication_batch as seeder


class AffiliateDirectPublisherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = publisher.load_manifest()

    def test_reviewed_manifest_renders_ten_substantive_pages(self):
        artifacts = publisher.validate_all(self.manifest)["artifacts"]
        self.assertEqual(len(artifacts), 10)
        self.assertTrue(all(item["visible_characters"] >= 850 for item in artifacts))
        self.assertEqual(len({item["artifact_hash"] for item in artifacts}), 10)

    def test_render_has_exact_disclosure_and_tracking_contract(self):
        item = self.manifest["items"][0]
        body = publisher.render_page(item, self.manifest["base_url"])
        self.assertEqual(body.count(publisher.DISCLOSURE), 1)
        self.assertEqual(body.count(item["product"]["affiliate_url"]), 1)
        self.assertIn('rel="sponsored nofollow"', body)
        self.assertIn(f'data-link-key="{item["product"]["tracking_key"]}"', body)

    def test_public_hash_allows_only_ci_site_verification_meta(self):
        item = self.manifest["items"][0]
        body = publisher.render_page(item, self.manifest["base_url"])
        deployed = body.replace('</head>', '<meta name="google-site-verification" content="publicVerificationToken_123"></head>')
        self.assertEqual(publisher.normalize_deployed_html(deployed), body)
        with self.assertRaisesRegex(publisher.PermanentError, "unexpected site-verification"):
            publisher.normalize_deployed_html(deployed.replace('</body>', '<meta name="google-site-verification" content="anotherToken_123"></body>'))

    def test_manifest_rejects_unverified_link(self):
        changed = copy.deepcopy(self.manifest)
        changed["items"][0]["product"]["affiliate_url"] = "https://link.coupang.com/a/not-reviewed"
        with self.assertRaisesRegex(publisher.PermanentError, "pre-verified"):
            publisher.validate_manifest(changed)

    def test_manifest_rejects_volume_above_daily_cap(self):
        changed = copy.deepcopy(self.manifest)
        changed["items"][3]["scheduled_at"] = "2026-09-14T21:00:00+09:00"
        with self.assertRaisesRegex(publisher.PermanentError, "daily_limit"):
            publisher.validate_manifest(changed)

    def test_hub_update_is_idempotent_and_removes_stale_count(self):
        item = self.manifest["items"][0]
        original = '<title>카테고리별 구매 체크리스트 10선 | Atemoya</title><h1>사기 전에 확인할<br />10개 카테고리 체크리스트</h1><main>  </main>'
        once = publisher.update_hub(original, item)
        twice = publisher.update_hub(once, item)
        self.assertEqual(once, twice)
        self.assertEqual(once.count(item["slug"] + ".html"), 1)
        self.assertNotIn("10선", once)
        self.assertNotIn("10개 카테고리", once)

    def test_seed_contract_is_direct_and_does_not_create_approval(self):
        sql = seeder.build_seed_sql(self.manifest)
        self.assertIn("direct_user_instruction", sql)
        self.assertIn("direct_affiliate_publish", sql)
        self.assertIn("daily_publication_limit", sql)
        self.assertIn("IS DISTINCT FROM EXCLUDED.rules", sql)
        self.assertNotIn("INSERT INTO public.approvals", sql)
        self.assertNotIn("INSERT INTO approval_requests", sql)

    @mock.patch.object(publisher, "db_json", return_value=[])
    def test_dispatch_waits_while_a_previous_deployment_is_unverified(self, db_json):
        self.assertIsNone(publisher.select_job(False))
        statement = db_json.call_args.args[0]
        self.assertIn("dp.state='deploying'", statement)

    @mock.patch.object(publisher, "db")
    def test_unbound_claim_fails_closed_and_releases_lease(self, db):
        publisher.mark_unbound_failure({"id": 7, "fence_token": 3}, publisher.PermanentError("manifest mismatch"))
        statement = db.call_args.args[0]
        self.assertIn("state='manual_review'", statement)
        self.assertIn("lease_owner=NULL", statement)
        self.assertIn("manifest mismatch", statement)


if __name__ == "__main__":
    unittest.main()
