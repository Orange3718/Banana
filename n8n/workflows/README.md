# n8n workflow exports

This folder stores reviewable workflow JSON, never credentials. Credential
references are names only and must be mapped to the existing credentials in the
n8n UI after import. Imported workflows must remain inactive until reviewed.

- `business-scout.json`: scheduled collection, deduplication, evaluation
  placeholder, PostgreSQL persistence and Telegram summary.
- `business-scout-error-handler.json`: workflow error logging and Telegram alert.
- `exports/`: sanitized exports from the live server may be copied here after
  review; do not export credentials.
- `exports/AtemoyaAffiliateHealth01.json`: daily public affiliate-page health
  check. It verifies reachability, the Coupang disclosure and the sponsored
  destination link, then records the result in PostgreSQL and reports to
  Telegram. The chat identifier is referenced through the private n8n variable
  `ATEMOYA_TELEGRAM_CHAT_ID`; it is not stored in this export. The workflow
  never clicks the affiliate link or reads settlement data.
- `exports/AtemoyaOpsGuardian01.json`: daily 03:10 deterministic operations
  review with a local Qwen summary, plus the deduplicated incident webhook used
  by the macOS Watchdog. It stores daily reviews before sending Telegram and
  never changes the rule-based `GOOD / REVIEW / BAD` verdict.
