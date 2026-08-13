# n8n workflow exports

This folder stores reviewable workflow JSON, never credentials. Credential
references are names only and must be mapped to the existing credentials in the
n8n UI after import. Imported workflows must remain inactive until reviewed.

- `business-scout.json`: scheduled collection, deduplication, evaluation
  placeholder, PostgreSQL persistence and Telegram summary.
- `business-scout-error-handler.json`: workflow error logging and Telegram alert.
- `exports/`: sanitized exports from the live server may be copied here after
  review; do not export credentials.
