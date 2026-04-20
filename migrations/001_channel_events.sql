CREATE TABLE IF NOT EXISTS channel_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    direction   TEXT NOT NULL,
    channel     TEXT NOT NULL,
    sender_id   TEXT,
    recipient_id TEXT,
    message_id  TEXT,
    event_type  TEXT NOT NULL,
    content     TEXT,
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
