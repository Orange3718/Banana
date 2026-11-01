# Atemoya operating instructions

This repository is the source for Atemoya code, workflow exports, schema, and operating rules. The iMac runs production; PostgreSQL records execution and business facts. Conversation history and dated status notes are context, not live state.

Before changing Atemoya operations, read `docs/OPERATING_CONTRACT.md`, run `scripts/preflight.sh`, and inspect only the files relevant to the request. Preserve unrelated worktree changes and take an `ops/scripts/backup.sh` snapshot before changing live n8n or PostgreSQL.

The owner retired Coupang Partners on 2026-11-02. The ten direct affiliate publication jobs are historical; do not reactivate their publisher, outbox notification, links, or per-post gate. New batches, account authentication, legal consent, spending, and unrelated trading need their own scope. The owner reported 0 KRW revenue on 2026-11-01; published pages alone are not evidence of a profitable loop.

Treat a Mac screen lock as a native GUI boundary, not a server outage. Use `scripts/preflight.sh`, Docker/launchctl, PostgreSQL, and HTTP APIs for status, repair, workflow imports, and verification without asking the owner to unlock. A browser tab may remain remotely accessible while the screen is locked; check the actual tab before treating web editing as blocked. Ask the owner to act only for account login, 2FA, or a native app GUI that the lock actually prevents. Distinguish screen lock from logout or reboot: current Docker Desktop and LaunchAgents start in the user's login session, so unattended boot recovery is not yet verified. See `docs/REMOTE_HEADLESS_OPERATING_MODEL.md`.

Use one Telegram inbound router and one registered scheduler per job. Restrict state-changing Telegram requests to the owner and deduplicate update IDs. Never let a model execute arbitrary shell or SQL from a message. Record source, request ID, action, target, authorization scope, and evidence for operational changes.

Use `docs/OPEN_ITEMS.md` for the current queue, then confirm each claim against live state. Report observed outcomes and remaining gaps. An active workflow, unit test, or successful push by itself is not an end-to-end acceptance test.
