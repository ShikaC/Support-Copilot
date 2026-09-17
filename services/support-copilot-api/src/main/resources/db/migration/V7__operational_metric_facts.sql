ALTER TABLE tickets ADD COLUMN resolved_at TIMESTAMP(6) NULL;
ALTER TABLE analysis_runs ADD COLUMN duration_ms BIGINT NULL;
CREATE INDEX idx_ticket_status_sla ON tickets (status, sla_deadline, id);
CREATE INDEX idx_ticket_resolved_at ON tickets (resolved_at);
CREATE INDEX idx_analysis_created_duration ON analysis_runs (created_at, duration_ms);
CREATE INDEX idx_ticket_sla_queue ON tickets (sla_deadline, created_at, id);
CREATE INDEX idx_ticket_assignee_queue ON tickets (assignee_name, created_at, id);
