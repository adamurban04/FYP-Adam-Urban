-- draft postgres tables for the next implementation stage
-- this file has not been applied to a running database

CREATE TABLE reconciliation_cases (
    case_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('open', 'match', 'review')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE case_transactions (
    case_id TEXT NOT NULL REFERENCES reconciliation_cases(case_id),
    source TEXT NOT NULL CHECK (source IN ('ledger', 'bank')),
    transaction_id TEXT NOT NULL,
    reference TEXT NOT NULL,
    amount_cents BIGINT NOT NULL,
    booking_date DATE NOT NULL,
    PRIMARY KEY (case_id, source, transaction_id)
);

CREATE TABLE audit_events (
    event_id BIGSERIAL PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES reconciliation_cases(case_id),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL
);

-- append-only permissions and recovery still need to be implemented
