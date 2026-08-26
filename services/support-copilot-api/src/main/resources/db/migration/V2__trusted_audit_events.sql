CREATE TABLE audit_events (
    id VARCHAR(64) NOT NULL,
    actor_subject VARCHAR(128) NOT NULL,
    actor_type VARCHAR(32) NOT NULL,
    actor_roles_json VARCHAR(512) NOT NULL,
    action VARCHAR(64) NOT NULL,
    target_type VARCHAR(48) NOT NULL,
    target_id VARCHAR(255) NOT NULL,
    target_version BIGINT,
    trace_id VARCHAR(64) NOT NULL,
    metadata_json LONGTEXT NOT NULL,
    created_at DATETIME(6) NOT NULL,
    CONSTRAINT pk_audit_events PRIMARY KEY (id)
);

CREATE INDEX idx_audit_events_created
    ON audit_events (created_at DESC, id DESC);

CREATE INDEX idx_audit_events_target_created
    ON audit_events (target_type, target_id, created_at DESC, id DESC);
