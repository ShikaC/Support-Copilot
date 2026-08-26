CREATE TABLE tickets (
    id VARCHAR(255) NOT NULL,
    ticket_no VARCHAR(32) NOT NULL,
    channel VARCHAR(32) NOT NULL,
    customer_name VARCHAR(80) NOT NULL,
    customer_company VARCHAR(120) NOT NULL,
    customer_tier VARCHAR(32) NOT NULL,
    subject VARCHAR(240) NOT NULL,
    description VARCHAR(4000) NOT NULL,
    language VARCHAR(16) NOT NULL,
    category VARCHAR(48) NOT NULL,
    priority VARCHAR(16) NOT NULL,
    status VARCHAR(48) NOT NULL,
    assignee_name VARCHAR(80),
    sla_deadline DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    version BIGINT NOT NULL,
    CONSTRAINT pk_tickets PRIMARY KEY (id),
    CONSTRAINT uk_tickets_ticket_no UNIQUE (ticket_no)
);

CREATE TABLE analysis_runs (
    id VARCHAR(255) NOT NULL,
    ticket_id VARCHAR(48) NOT NULL,
    source_ticket_version BIGINT NOT NULL,
    trace_id VARCHAR(64) NOT NULL,
    status VARCHAR(24) NOT NULL,
    mode VARCHAR(24) NOT NULL,
    fallback_reason VARCHAR(64),
    response_json LONGTEXT NOT NULL,
    created_at DATETIME(6) NOT NULL,
    CONSTRAINT pk_analysis_runs PRIMARY KEY (id)
);

CREATE INDEX idx_analysis_runs_ticket_created
    ON analysis_runs (ticket_id, created_at);

CREATE TABLE analysis_reviews (
    id VARCHAR(255) NOT NULL,
    ticket_id VARCHAR(48) NOT NULL,
    analysis_id VARCHAR(64) NOT NULL,
    action VARCHAR(24) NOT NULL,
    reviewer_type VARCHAR(32) NOT NULL,
    reviewer_label VARCHAR(80) NOT NULL,
    original_reply_content LONGTEXT NOT NULL,
    reviewed_reply_content LONGTEXT,
    reason LONGTEXT,
    ticket_version BIGINT NOT NULL,
    trace_id VARCHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    CONSTRAINT pk_analysis_reviews PRIMARY KEY (id)
);

CREATE INDEX idx_analysis_reviews_analysis_created
    ON analysis_reviews (analysis_id, created_at);

CREATE INDEX idx_analysis_reviews_ticket
    ON analysis_reviews (ticket_id);
