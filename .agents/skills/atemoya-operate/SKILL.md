---
name: atemoya-operate
description: Operate, diagnose, or extend the Atemoya iMac revenue system from this repository, including Telegram, n8n, PostgreSQL, affiliate measurement, and remote control.
---

# Atemoya operation

Open the repository root. Read `AGENTS.md` and `docs/OPERATING_CONTRACT.md`, then run `scripts/preflight.sh`. Use PostgreSQL and live service checks for current state; dated notes are historical. Preserve unrelated worktree changes. Run `ops/scripts/backup.sh` before changing production schema or n8n workflows. Verify the actual inbound, execution, database, and outbound path relevant to the task. Record results in `docs/OPEN_ITEMS.md` and report observed facts, unknowns, rollback, and the next action. Do not install another scheduler or Telegram trigger.
