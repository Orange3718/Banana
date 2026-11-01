-- The owner allowlist is seeded locally, never inferred from an incoming update.
CREATE TABLE IF NOT EXISTS public.telegram_owner_actors (
  actor_id BIGINT NOT NULL,
  chat_id BIGINT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT true,
  added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (actor_id, chat_id)
);

CREATE TABLE IF NOT EXISTS public.telegram_update_receipts (
  update_id BIGINT PRIMARY KEY,
  actor_id BIGINT NOT NULL,
  chat_id BIGINT NOT NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  source TEXT NOT NULL DEFAULT 'AtemoyaTelegramMemory01'
);

CREATE INDEX IF NOT EXISTS telegram_update_receipts_received_at_idx
  ON public.telegram_update_receipts (received_at DESC);
