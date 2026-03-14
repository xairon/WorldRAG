-- Migration 001: chat_feedback table
-- Stores user thumbs-up/thumbs-down ratings on chat answers.

CREATE TABLE IF NOT EXISTS chat_feedback (
    id          BIGSERIAL PRIMARY KEY,
    thread_id   TEXT        NOT NULL,
    message_id  TEXT,
    rating      SMALLINT    NOT NULL CHECK (rating IN (-1, 1)),
    comment     TEXT,
    book_id     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS chat_feedback_thread_id_idx
    ON chat_feedback (thread_id);
