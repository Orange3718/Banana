#!/usr/bin/env python3
"""Save a Drive/local source file privately and record its hash without financial posting."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


MAX_BYTES = 20_000_000
RECEIPT_ROOT = Path("/Users/orange/Atemoya/intake")
ALLOWED_SUFFIXES = {".xlsx", ".csv", ".txt", ".pdf", ".png", ".jpg", ".jpeg"}


def save_receipt(source: Path, digest: str, suffix: str) -> Path:
    RECEIPT_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    if RECEIPT_ROOT.is_symlink() or RECEIPT_ROOT.stat().st_mode & 0o077:
        raise ValueError("Receipt directory must be private (0700)")
    destination = RECEIPT_ROOT / (digest + suffix)
    data = source.read_bytes()
    try:
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if destination.is_symlink() or destination.read_bytes() != data:
            raise ValueError("Receipt hash conflict")
    else:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    return destination


def record(payload: dict) -> dict:
    sql = """WITH p AS (SELECT :'payload'::jsonb AS x), inserted AS (
      INSERT INTO affiliate.intake_files(source_system,source_file_id,source_name,mime_type,provider,report_family,sha256,byte_count,receipt_path,state,inspection)
      SELECT x->>'source_system',x->>'source_file_id',x->>'source_name',x->>'mime_type',NULLIF(x->>'provider',''),NULLIF(x->>'report_family',''),x->>'sha256',(x->>'byte_count')::bigint,x->>'receipt_path',x->>'state',x->'inspection' FROM p
      ON CONFLICT(source_system,source_file_id,sha256) DO NOTHING RETURNING id
    ) SELECT id,'inserted' AS action FROM inserted UNION ALL
      SELECT f.id,'existing' AS action FROM affiliate.intake_files f,p
      WHERE f.source_system=p.x->>'source_system' AND f.source_file_id=p.x->>'source_file_id' AND f.sha256=p.x->>'sha256' AND NOT EXISTS(SELECT 1 FROM inserted);"""
    cmd = ["docker", "exec", "-i", "atemoya-postgres", "psql", "-X", "-v", "ON_ERROR_STOP=1", "-v", "payload=" + json.dumps(payload, ensure_ascii=False), "-U", "n8n", "-d", "n8n", "-At"]
    result = subprocess.run(cmd, input=sql, text=True, capture_output=True, check=True)
    row = result.stdout.strip().split("|")
    if len(row) != 2:
        raise RuntimeError("Unexpected intake database response")
    return {"id": int(row[0]), "action": row[1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--source-system", choices=("google_drive", "local"), required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--mime", required=True)
    parser.add_argument("--provider", default="")
    parser.add_argument("--report-family", default="")
    args = parser.parse_args()
    if not args.source.is_file() or args.source.is_symlink():
        parser.error("Source must be a regular file, not a symlink")
    if not 1 <= len(args.source_id) <= 256 or not re.fullmatch(r"[A-Za-z0-9_-]+", args.source_id):
        parser.error("Invalid source ID")
    size = args.source.stat().st_size
    if size > MAX_BYTES:
        parser.error("Source exceeds 20 MB")
    suffix = Path(args.source_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        parser.error("Unsupported source type")
    data = args.source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    receipt = save_receipt(args.source, digest, suffix)
    inspection = {"financial_posting": False}
    state = "received"
    if args.provider == "coupang" and suffix == ".xlsx":
        from inspect_coupang_report import inspect_report

        try:
            inspection["report_inspection"] = inspect_report(data)
            if inspection["report_inspection"]["state"] == "mapping_required":
                state = "quarantined"
        except (ValueError, KeyError, OSError) as exc:
            inspection["error"] = str(exc)[:400]
            state = "quarantined"
    payload = {
        "source_system": args.source_system,
        "source_file_id": args.source_id,
        "source_name": Path(args.source_name).name,
        "mime_type": args.mime,
        "provider": args.provider,
        "report_family": args.report_family,
        "sha256": digest,
        "byte_count": len(data),
        "receipt_path": str(receipt),
        "state": state,
        "inspection": inspection,
    }
    result = record(payload)
    print(json.dumps({"intake_id": result["id"], "action": result["action"], "sha256": digest, "bytes": len(data), "state": state, "inspection": inspection.get("report_inspection", {}).get("state"), "financial_posting": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
