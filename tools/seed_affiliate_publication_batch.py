#!/usr/bin/env python3
"""Validate and seed a reviewed direct-affiliate publication manifest."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from affiliate_direct_publisher import (
    DEFAULT_MANIFEST,
    DISCLOSURE,
    item_digest,
    load_manifest,
    quote,
    render_page,
    sha256_text,
)


DB_STDIN_CMD = [
    "/usr/local/bin/docker", "exec", "-i", "atemoya-postgres", "psql",
    "-v", "ON_ERROR_STOP=1", "-U", "n8n", "-d", "n8n", "-At",
]


def build_seed_sql(manifest: dict) -> str:
    statements = [
        "BEGIN;",
        """
DO $batch$
DECLARE
  v_account BIGINT;
  v_policy BIGINT;
  v_experiment BIGINT;
  v_asset BIGINT;
  v_content BIGINT;
  v_revision BIGINT;
  v_offer BIGINT;
  v_existing_hash CHAR(64);
  v_existing_url TEXT;
  v_publication BIGINT;
BEGIN
  INSERT INTO affiliate.program_accounts(environment,provider,account_ref,market,state,credential_ref)
  VALUES('prod','coupang_partners','primary-manual-link-account','KR','ready',NULL)
  ON CONFLICT(environment,provider,account_ref) DO UPDATE SET market=EXCLUDED.market,state='ready'
  RETURNING id INTO v_account;

  INSERT INTO affiliate.policy_versions(account_id,version,source_ref,verified_at,capabilities,contract)
  VALUES(
    v_account,1,'coupang-partners-portal:manual-link-and-disclosure',TIMESTAMPTZ '2026-09-14 06:20:00+09',
    jsonb_build_object('manual_deeplink',true,'product_api',false,'report_download',true),
    jsonb_build_object('affiliate_host','link.coupang.com','required_disclosure',""" + quote(DISCLOSURE) + """,'market','KR')
  ) ON CONFLICT(account_id,version) DO NOTHING;
  SELECT id INTO v_policy FROM affiliate.policy_versions WHERE account_id=v_account AND version=1;

  INSERT INTO public.experiments(name,hypothesis,status,started_at,success_metric,target_value,result)
  SELECT 'Coupang verified-link volume pilot 2026-09',
    '검색 의도별로 유용한 구매 판단 글을 규칙적으로 공개하면 자연 유입과 정상 외부 판매 표본을 만들 수 있다.',
    'running',TIMESTAMPTZ '2026-09-14 09:00:00+09','qualified affiliate clicks and externally reported sales',NULL,
    jsonb_build_object('batch_key',""" + quote(manifest["batch_key"]) + """,'baseline_sales_krw',0,'measurement_state','awaiting_natural_traffic')
  WHERE NOT EXISTS (SELECT 1 FROM public.experiments WHERE name='Coupang verified-link volume pilot 2026-09');
  SELECT id INTO v_experiment FROM public.experiments WHERE name='Coupang verified-link volume pilot 2026-09' ORDER BY id LIMIT 1;

  INSERT INTO affiliate.experiment_extensions(experiment_id,primary_account_id,market,locale,state_version,rules,budget)
  VALUES(v_experiment,v_account,'KR','ko-KR',1,
    jsonb_build_object('version',1,'success_metric','externally_reported_sales','minimum_sample',NULL,'report_maturity_policy','Coupang report maturity','decision_cadence','daily','maximum_assets',10,'daily_publication_limit',""" + str(manifest["daily_limit"]) + """),
    jsonb_build_object('reporting_currency','KRW','monthly_cash_cap',0,'experiment_cash_cap',0,'owner_minutes_target',0))
  ON CONFLICT(experiment_id) DO UPDATE SET
    state_version=CASE
      WHEN affiliate.experiment_extensions.rules IS DISTINCT FROM EXCLUDED.rules OR affiliate.experiment_extensions.budget IS DISTINCT FROM EXCLUDED.budget
      THEN affiliate.experiment_extensions.state_version+1 ELSE affiliate.experiment_extensions.state_version END,
    rules=EXCLUDED.rules,budget=EXCLUDED.budget;

  INSERT INTO public.assets(experiment_id,slug,name,asset_type,status,canonical_url,repository_path,metadata)
  VALUES(v_experiment,'coupang-volume-pilot-20260914','Coupang Direct Publication Volume Pilot','affiliate_content_batch','active',
    'https://orange3718.github.io/Banana/offers/','offers/',jsonb_build_object('batch_key',""" + quote(manifest["batch_key"]) + """,'authorization_mode','direct_user_instruction'))
  ON CONFLICT(slug) DO UPDATE SET experiment_id=EXCLUDED.experiment_id,status='active',metadata=EXCLUDED.metadata
  RETURNING id INTO v_asset;
""",
    ]

    for item in manifest["items"]:
        product = item["product"]
        document = render_page(item, manifest["base_url"])
        artifact_hash = sha256_text(document)
        public_path = "offers/" + item["slug"] + ".html"
        destination_url = "https://www.coupang.com/vp/products/" + product["item_id"]
        payload = {
            "manifest_schema_version": manifest["schema_version"],
            "batch_key": manifest["batch_key"],
            "publication_key": item["publication_key"],
            "scheduled_at": item["scheduled_at"],
            "public_path": public_path,
            "category": item["category"],
            "title": item["title"],
            "daily_limit": manifest["daily_limit"],
            "authorization_mode": manifest["authorization_mode"],
            "target": manifest["target"],
        }
        metadata = {
            "batch_key": manifest["batch_key"],
            "publication_key": item["publication_key"],
            "category": item["category"],
            "product_item_id": product["item_id"],
            "tracking_key": product["tracking_key"],
            "scheduled_at": item["scheduled_at"],
            "authorization_mode": "direct_user_instruction",
        }
        evidence = [{
            "claim_id": "verified-affiliate-link-binding",
            "source_ref": "docs/affiliate-os/16-ten-category-publication-plan.md",
            "observed_at": "2026-09-14T06:20:00+09:00",
            "claim_text_hash": sha256_text(product["item_id"] + ":" + product["affiliate_url"]),
            "applicable_market": "KR",
            "valid_until": None,
            "review_trigger": "link redirect, product availability, or Coupang policy changes",
            "rights_reference": "Coupang Partners direct-link tool",
        }]
        statements.append(f"""
  INSERT INTO public.content(asset_id,external_key,title,channel,status,source_url,body_ref,metadata)
  VALUES(v_asset,{quote(item['publication_key'])},{quote(item['title'])},'github_pages','ready',{quote(destination_url)},{quote(public_path)},{quote(json.dumps(metadata, ensure_ascii=False))}::jsonb)
  ON CONFLICT(external_key) DO UPDATE SET
    asset_id=EXCLUDED.asset_id,title=EXCLUDED.title,source_url=EXCLUDED.source_url,body_ref=EXCLUDED.body_ref,
    metadata=EXCLUDED.metadata,status=CASE WHEN public.content.status='published' THEN public.content.status ELSE 'ready' END,updated_at=now()
  RETURNING id INTO v_content;

  INSERT INTO affiliate.content_extensions(content_id,experiment_id,primary_category,locale,target_market,publisher_owner)
  VALUES(v_content,v_experiment,{quote(item['category'])},'ko-KR','KR','atemoya-direct-publisher')
  ON CONFLICT(content_id) DO UPDATE SET primary_category=EXCLUDED.primary_category,locale=EXCLUDED.locale,target_market=EXCLUDED.target_market,publisher_owner=EXCLUDED.publisher_owner;

  INSERT INTO affiliate.content_revisions(content_id,revision_no,body_text,body_sha256,evidence,template_version)
  VALUES(v_content,1,{quote(document)},{quote(artifact_hash)},{quote(json.dumps(evidence, ensure_ascii=False))}::jsonb,'direct-affiliate-v1')
  ON CONFLICT(content_id,revision_no) DO NOTHING;
  SELECT id,body_sha256 INTO v_revision,v_existing_hash FROM affiliate.content_revisions WHERE content_id=v_content AND revision_no=1;
  IF v_existing_hash <> {quote(artifact_hash)} THEN
    RAISE EXCEPTION 'immutable revision hash mismatch for %', {quote(item['publication_key'])};
  END IF;

  INSERT INTO affiliate.offers(account_id,external_item_id,destination_url,current_state,checked_at)
  VALUES(v_account,{quote(product['item_id'])},{quote(destination_url)},'verified',TIMESTAMPTZ '2026-09-14 06:20:00+09')
  ON CONFLICT(account_id,external_item_id) DO UPDATE SET destination_url=EXCLUDED.destination_url,current_state='verified',checked_at=EXCLUDED.checked_at
  RETURNING id INTO v_offer;

  INSERT INTO affiliate.link_versions(revision_id,offer_id,placement_key,affiliate_url,policy_version_id,tracking_key,evidence_ref)
  VALUES(v_revision,v_offer,'primary-cta',{quote(product['affiliate_url'])},v_policy,{quote(product['tracking_key'])},'docs/affiliate-os/16-ten-category-publication-plan.md')
  ON CONFLICT(revision_id,placement_key) DO NOTHING;
  SELECT affiliate_url INTO v_existing_url FROM affiliate.link_versions WHERE revision_id=v_revision AND placement_key='primary-cta';
  IF v_existing_url <> {quote(product['affiliate_url'])} THEN
    RAISE EXCEPTION 'immutable affiliate link mismatch for %', {quote(item['publication_key'])};
  END IF;

  INSERT INTO affiliate.publications(revision_id,approval_id,target,idempotency_key,state,artifact_hash,authorization_mode)
  VALUES(v_revision,NULL,{quote(manifest['target'])},{quote(item['publication_key'])},'queued',{quote(artifact_hash)},'direct_user_instruction')
  ON CONFLICT(idempotency_key) DO NOTHING;
  SELECT id INTO v_publication FROM affiliate.publications
    WHERE idempotency_key={quote(item['publication_key'])} AND revision_id=v_revision AND artifact_hash={quote(artifact_hash)} AND authorization_mode='direct_user_instruction';
  IF v_publication IS NULL THEN
    RAISE EXCEPTION 'publication binding mismatch for %', {quote(item['publication_key'])};
  END IF;

  INSERT INTO affiliate.jobs(kind,job_key,payload_hash,state,attempt,max_attempts,next_attempt_at,payload,correlation_id)
  VALUES('direct_affiliate_publish',{quote(item['publication_key'])},{quote(item_digest(item))},'queued',0,3,{quote(item['scheduled_at'])}::timestamptz,{quote(canonical_json(payload))}::jsonb,{quote(item['publication_key'])})
  ON CONFLICT(job_key) DO UPDATE SET
    payload_hash=EXCLUDED.payload_hash,payload=EXCLUDED.payload,
    state=CASE WHEN affiliate.jobs.state IN ('running','succeeded','manual_review','failed','cancelled') THEN affiliate.jobs.state ELSE 'queued' END,
    next_attempt_at=CASE WHEN affiliate.jobs.state IN ('running','succeeded','manual_review','failed','cancelled') THEN affiliate.jobs.next_attempt_at ELSE EXCLUDED.next_attempt_at END,
    updated_at=now();
""")

    statements.extend([
        """
END $batch$;
""",
        "COMMIT;",
    ])
    return "\n".join(statements)


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def apply_sql(sql: str) -> str:
    result = subprocess.run(DB_STDIN_CMD, input=sql, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    summary = {
        "status": "validated",
        "batch_key": manifest["batch_key"],
        "authorization_mode": manifest["authorization_mode"],
        "daily_limit": manifest["daily_limit"],
        "items": [
            {
                "publication_key": item["publication_key"],
                "scheduled_at": item["scheduled_at"],
                "artifact_hash": sha256_text(render_page(item, manifest["base_url"])),
            }
            for item in manifest["items"]
        ],
    }
    if args.apply:
        apply_sql(build_seed_sql(manifest))
        summary["status"] = "seeded"
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
