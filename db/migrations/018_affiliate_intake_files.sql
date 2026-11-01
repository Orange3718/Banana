-- Raw source receipts are not financial facts. Revisions of one Drive file keep distinct hashes.
CREATE TABLE IF NOT EXISTS affiliate.intake_files (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_system TEXT NOT NULL CHECK (source_system IN ('google_drive','local')),
  source_file_id TEXT NOT NULL,
  source_name TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  provider TEXT,
  report_family TEXT,
  sha256 CHAR(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  byte_count BIGINT NOT NULL CHECK (byte_count >= 0),
  receipt_path TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'received' CHECK (state IN ('received','quarantined','mapped')),
  inspection JSONB NOT NULL DEFAULT '{}'::jsonb,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source_system, source_file_id, sha256)
);

CREATE INDEX IF NOT EXISTS intake_files_captured_at_idx ON affiliate.intake_files(captured_at DESC);
