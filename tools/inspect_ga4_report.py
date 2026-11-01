#!/usr/bin/env python3
"""Inspect the observed GA4 CSV exports without treating them as daily or sales facts."""

import csv
from datetime import datetime
import io


PAGE_HEADERS = (
    "페이지 경로 및 화면 클래스", "조회수", "활성 사용자", "활성 사용자당 조회수",
    "활성 사용자당 평균 참여 시간", "이벤트 수", "주요 이벤트", "총수익",
)
EVENT_HEADERS = ("이벤트 이름", "이벤트 수", "총 사용자", "활성 사용자당 이벤트 수", "총수익")
MAX_ROWS = 10_000


def nonnegative_int(value: str) -> int:
    if not value.isascii() or not value.isdecimal():
        raise ValueError("GA4 count is not a nonnegative integer")
    return int(value)


def inspect_report(data: bytes, property_id: str, measurement_id: str) -> dict:
    if not property_id.isascii() or not property_id.isdecimal():
        raise ValueError("GA4 property ID must be numeric")
    if not measurement_id.startswith("G-") or not measurement_id[2:].isascii() or not measurement_id[2:].isalnum():
        raise ValueError("Invalid GA4 measurement ID")
    if len(data) > 20_000_000:
        raise ValueError("GA4 report exceeds 20 MB")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("GA4 report must be UTF-8 CSV") from exc
    rows = csv.reader(io.StringIO(text, newline=""), strict=True)
    metadata = {}
    header = None
    values = []
    for row in rows:
        if len(row) == 1 and row[0].startswith("#") and header is None:
            label, sep, value = row[0][1:].strip().partition(":")
            if sep:
                metadata[label.strip()] = value.strip()
            continue
        if not row or row == [""]:
            continue
        if header is None:
            header = tuple(row)
            if header not in (PAGE_HEADERS, EVENT_HEADERS):
                raise ValueError("Unknown GA4 CSV column contract")
            continue
        if len(row) != len(header) or any(not cell for cell in row):
            raise ValueError("Incomplete GA4 CSV row")
        values.append(row)
        if len(values) > MAX_ROWS:
            raise ValueError("GA4 CSV row limit exceeded")
    if header is None or metadata.get("계정") != "Atemoya" or metadata.get("속성") != "Atemoya":
        raise ValueError("GA4 export is not labelled as the Atemoya property")
    try:
        start = datetime.strptime(metadata["시작일"], "%Y%m%d").date()
        end = datetime.strptime(metadata["종료일"], "%Y%m%d").date()
    except (KeyError, ValueError) as exc:
        raise ValueError("Invalid GA4 report period") from exc
    if start > end:
        raise ValueError("GA4 report period is reversed")

    seen = set()
    for row in values:
        if row[0] in seen:
            raise ValueError("Duplicate GA4 dimension row")
        seen.add(row[0])
    result = {
        "state": "observed" if values else "empty_report", "grain": "period_aggregate", "daily_metric_eligible": False,
        "financial_posting": False, "property_id": property_id, "measurement_id": measurement_id,
        "period_start": start.isoformat(), "period_end": end.isoformat(), "row_count": len(values),
    }
    if header == PAGE_HEADERS:
        views = [nonnegative_int(row[1]) for row in values]
        result.update({"report_type": "page_paths", "page_views": sum(views),
                       "affiliate_page_views": sum(count for row, count in zip(values, views) if row[0].startswith("/Banana/offers/")),
                       "page_paths": [row[0] for row in values]})
    else:
        counts = {row[0]: nonnegative_int(row[1]) for row in values}
        result.update({"report_type": "event_names", "event_count": sum(counts.values()),
                       "event_names": sorted(counts),
                       "affiliate_click_listed": "affiliate_click" in counts,
                       "affiliate_click_reported": counts.get("affiliate_click")})
    return result
