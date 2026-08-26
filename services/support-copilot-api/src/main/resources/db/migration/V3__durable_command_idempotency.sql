CREATE TABLE command_idempotency (
    id VARCHAR(64) NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    request_fingerprint CHAR(64) NOT NULL,
    command_type VARCHAR(32) NOT NULL,
    route_scope VARCHAR(160) NOT NULL,
    status VARCHAR(16) NOT NULL,
    owner_token VARCHAR(64),
    lease_expires_at DATETIME(6),
    response_http_status INTEGER,
    response_json LONGTEXT,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    completed_at DATETIME(6),
    CONSTRAINT pk_command_idempotency PRIMARY KEY (id),
    CONSTRAINT uk_command_idempotency_key UNIQUE (idempotency_key)
);

CREATE INDEX idx_command_idempotency_pending_lease
    ON command_idempotency (status, lease_expires_at);

CREATE INDEX idx_command_idempotency_updated
    ON command_idempotency (updated_at);
