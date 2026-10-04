BEGIN;

-- Generic relationship table between operational-memory rows, so a local
-- model can record "이 두 항목은 관련 있다" without needing a foreign key
-- into every possible source table. from_type/to_type name the table the
-- id came from (as text ids, since local_llm_runs uses run_key and others
-- use bigint) so the Obsidian export script can join back for display.
CREATE TABLE IF NOT EXISTS vault_links (
  id bigserial PRIMARY KEY,
  from_type text NOT NULL,
  from_id text NOT NULL,
  to_type text NOT NULL,
  to_id text NOT NULL,
  relation text NOT NULL,
  reason text NOT NULL,
  confidence real,
  provider text NOT NULL DEFAULT 'ollama-local',
  model text NOT NULL DEFAULT 'qwen3.5:4b',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (from_type, from_id, to_type, to_id, relation)
);

CREATE INDEX IF NOT EXISTS vault_links_from_idx
  ON vault_links (from_type, from_id);
CREATE INDEX IF NOT EXISTS vault_links_to_idx
  ON vault_links (to_type, to_id);
CREATE INDEX IF NOT EXISTS vault_links_created_idx
  ON vault_links (created_at DESC);

COMMIT;
