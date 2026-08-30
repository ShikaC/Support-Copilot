ALTER TABLE tickets
    ADD CONSTRAINT ck_tickets_channel
        CHECK (channel IN ('EMAIL', 'CHAT', 'WEB_FORM', 'PHONE'));

ALTER TABLE tickets
    ADD CONSTRAINT ck_tickets_customer_tier
        CHECK (customer_tier IN ('STANDARD', 'PREMIUM', 'ENTERPRISE'));

ALTER TABLE tickets
    ADD CONSTRAINT ck_tickets_category
        CHECK (category IN (
            'UNCLASSIFIED', 'GENERAL', 'BILLING', 'ACCOUNT_ACCESS', 'INVOICE',
            'DATA_EXPORT', 'SUBSCRIPTION', 'PRIVACY', 'SECURITY', 'LEGAL',
            'TECHNICAL', 'DATA_RECOVERY'
        ));

ALTER TABLE tickets
    ADD CONSTRAINT ck_tickets_priority
        CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT'));

ALTER TABLE tickets
    ADD CONSTRAINT ck_tickets_status
        CHECK (status IN (
            'NEW', 'READY_FOR_REVIEW', 'READY_FOR_MANUAL_REVIEW', 'NEEDS_ESCALATION',
            'IN_PROGRESS', 'WAITING_CUSTOMER', 'RESOLVED', 'CLOSED'
        ));

CREATE INDEX idx_tickets_queue_created_id
    ON tickets (created_at, id);

CREATE INDEX idx_tickets_category_created_id
    ON tickets (category, created_at, id);

CREATE INDEX idx_tickets_status_created_id
    ON tickets (status, created_at, id);

CREATE INDEX idx_tickets_priority_created_id
    ON tickets (priority, created_at, id);

CREATE INDEX idx_analysis_runs_ticket_created_id
    ON analysis_runs (ticket_id, created_at, id);

CREATE INDEX idx_analysis_reviews_analysis_created_id
    ON analysis_reviews (analysis_id, created_at, id);
