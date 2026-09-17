CREATE TABLE ticket_notes (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    ticket_id VARCHAR(255) NOT NULL,
    request_id VARCHAR(36) NOT NULL,
    content VARCHAR(4000) NOT NULL,
    author_subject VARCHAR(255) NOT NULL,
    author_label VARCHAR(255) NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    CONSTRAINT uq_ticket_note_request UNIQUE (ticket_id, request_id),
    CONSTRAINT fk_ticket_notes_ticket FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);
CREATE INDEX idx_ticket_notes_ticket_created ON ticket_notes (ticket_id, created_at, id);
