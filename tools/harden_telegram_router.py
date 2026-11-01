#!/usr/bin/env python3
"""Put the owner and update-ID gate immediately after the single Telegram trigger."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "n8n/workflows/exports/AtemoyaTelegramMemory01.json"
TRIGGER = "Telegram 메시지 수신"
GATE = "Owner·중복 update 검증"

QUERY = """WITH allowed AS (
  SELECT $1::bigint AS update_id, $2::bigint AS actor_id,
         $3::bigint AS chat_id, $4::jsonb AS raw_update
  WHERE EXISTS (
    SELECT 1 FROM public.telegram_owner_actors o
    WHERE o.actor_id=$2::bigint AND o.chat_id=$3::bigint AND o.enabled
  )
), inserted AS (
  INSERT INTO public.telegram_update_receipts(update_id,actor_id,chat_id)
  SELECT update_id,actor_id,chat_id FROM allowed
  ON CONFLICT(update_id) DO NOTHING
  RETURNING update_id
)
SELECT a.update_id, a.raw_update->'message' AS message
FROM allowed a JOIN inserted i USING(update_id);"""


def harden(workflow):
    names = {node["name"] for node in workflow["nodes"]}
    if GATE in names:
        assert workflow["connections"][TRIGGER]["main"][0][0]["node"] == GATE
        return False
    assert TRIGGER in names
    original = workflow["connections"][TRIGGER]["main"]
    assert len(original) == 1 and len(original[0]) == 1
    workflow["nodes"].append({
        "parameters": {
            "operation": "executeQuery",
            "query": QUERY,
            "options": {"queryReplacement": "={{ [$json.update_id, $json.message?.from?.id, $json.message?.chat?.id, JSON.stringify($json)] }}"},
        },
        "id": "telegram-owner-update-gate-01",
        "name": GATE,
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.6,
        "position": [380, 300],
        "credentials": {"postgres": {"id": "AtemoyaPostgresMemory01", "name": "Atemoya PostgreSQL Memory"}},
    })
    workflow["connections"][TRIGGER]["main"] = [[{"node": GATE, "type": "main", "index": 0}]]
    workflow["connections"][GATE] = {"main": original}
    return True


def main():
    payload = json.loads(PATH.read_text())
    workflow = payload[0] if isinstance(payload, list) else payload
    changed = harden(workflow)
    if changed:
        PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    print("Telegram owner/update gate:", "added" if changed else "already present")


if __name__ == "__main__":
    main()
