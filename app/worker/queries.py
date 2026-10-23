from sqlalchemy import text

CLAIM_DUE_MONITORS = text("""
WITH due AS (
    SELECT id
    FROM monitors
    WHERE is_active = TRUE
      AND next_check_at <= NOW()
    ORDER BY next_check_at
    LIMIT :batch
    FOR UPDATE SKIP LOCKED
)
UPDATE monitors m
SET next_check_at = NOW()
                  + (m.interval_seconds * INTERVAL '1 second')
FROM due
WHERE m.id = due.id
RETURNING m.id, m.url, m.timeout_seconds, m.expected_status,
          m.failure_threshold, m.consecutive_failures, m.webhook_url;
""")
