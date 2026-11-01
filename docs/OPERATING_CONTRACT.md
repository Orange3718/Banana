# Atemoya operating contract

## Purpose and boundaries

Atemoya is an evidence-led business system. The owner retired Coupang Partners on 2026-11-02 after reporting 0 KRW revenue as of 2026-11-01. The old direct publisher, outbox notification, and affiliate links are parked; historical publications and financial records remain auditable. The next revenue model is undecided. Do not restart affiliate publication or add a provider without a new owner decision and a measured demand → offer → revenue → cash loop. Personal trading and company work have separate data, schedules, and approval scopes.

## Durable sources

| Concern | Source |
| --- | --- |
| Code, instructions, workflow exports | This Git repository |
| Jobs, publications, requests, financial facts | iMac PostgreSQL |
| Runtime scheduling | Existing n8n workflows and macOS LaunchAgents |
| Owner conversation and alerts | Telegram, through the single `AtemoyaTelegramMemory01` inbound workflow |
| Human decisions and reusable context | LifeOS, linked to Git commit or database evidence |
| Provider files | Private receipt storage, with Drive as a mobile inbox only after ingestion is configured |

Codex, Claude Code, and Antigravity should open this repository root and use this contract plus `AGENTS.md`. Their chat memories are not operational state. No IDE should register a second Telegram trigger or duplicate a runtime scheduler.

## Request and action contract

Every state-changing request needs `source`, `request_id`, `actor`, `domain`, `target_id`, `action`, `authorization_scope`, `idempotency_key`, `status`, and `evidence_refs`. Telegram natural language may identify intent; a deterministic gate decides allowed actions. Unknown sender, repeated update ID, missing target, and ambiguous instruction stop before mutation. The owner-authorized direct affiliate publication queue does not require per-item GOOD/BAD. New spending, account security steps, legal terms, and trading changes use their own explicit scope.

Secrets stay in local credential stores and never enter Git, Drive, Telegram, or LifeOS. A Telegram chat ID is a routing identifier, not authentication by itself; webhook transport must also be checked before treating the route as fully trusted. The old direct affiliate publication authorization ended with the 2026-11-02 business decision.

## Operating loop

1. `scripts/preflight.sh` reports live service, parked components, historical publication, measurement, and Telegram delivery status.
2. Repair the first broken dependency, then run the applicable end-to-end test.
3. Write execution results in PostgreSQL, publish a concise owner result through the outbox, and link durable decisions in LifeOS.
4. Weekly: inspect demand, visits, direct cost, owner time, any realized revenue, and each unknown value. Choose at most one new acquisition and offer experiment after an explicit business decision. Treat former Coupang records as history.

## Verification and rollback

Before live schema/workflow edits, run `ops/scripts/backup.sh` and keep the printed path. Apply additive migrations, deploy a versioned workflow, then verify health, single ownership, a real inbound/outbound round trip, and duplicate/unauthorized rejection. If a live check fails, restore the prior workflow export from the backup and keep volumes intact. Never claim Telegram is working solely because a workflow has `active=true`.

`docs/affiliate-os/11-execution-status.md` and dated sections of `docs/ATEMOYA_SYSTEM_BASELINE.md` are historical snapshots; use live DB counts for current numbers.
