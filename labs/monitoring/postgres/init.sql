-- Target schema for the ETL upsert.
-- One row per (product_id, minute_window). UNIQUE constraint enables ON CONFLICT.
CREATE TABLE IF NOT EXISTS aggregated_clicks (
    product_id     TEXT        NOT NULL,
    minute_window  TIMESTAMP   NOT NULL,
    click_count    BIGINT      NOT NULL,
    last_batch_id  TEXT        NOT NULL,
    updated_at     TIMESTAMP   NOT NULL DEFAULT now(),
    PRIMARY KEY (product_id, minute_window)
);

CREATE INDEX IF NOT EXISTS aggregated_clicks_window_idx
    ON aggregated_clicks (minute_window DESC);

CREATE INDEX IF NOT EXISTS aggregated_clicks_batch_idx
    ON aggregated_clicks (last_batch_id);
