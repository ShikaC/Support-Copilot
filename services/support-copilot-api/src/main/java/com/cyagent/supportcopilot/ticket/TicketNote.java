package com.cyagent.supportcopilot.ticket;

import java.time.Instant;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "ticket_notes", uniqueConstraints = @jakarta.persistence.UniqueConstraint(columnNames = {"ticket_id", "request_id"}))
@Getter
@NoArgsConstructor(access = lombok.AccessLevel.PROTECTED)
public class TicketNote {
    @Id
    @Column(length = 36)
    private String id;
    @Column(nullable = false, updatable = false)
    private String ticketId;
    @Column(nullable = false, updatable = false, length = 36)
    private String requestId;
    @Column(nullable = false, updatable = false, length = 4000)
    private String content;
    @Column(nullable = false, updatable = false, length = 255)
    private String authorSubject;
    @Column(nullable = false, updatable = false, length = 255)
    private String authorLabel;
    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    public TicketNote(String id, String ticketId, String requestId, String content, String authorSubject, String authorLabel, Instant createdAt) {
        this.id = id;
        this.ticketId = ticketId;
        this.requestId = requestId;
        this.content = content;
        this.authorSubject = authorSubject;
        this.authorLabel = authorLabel;
        this.createdAt = createdAt;
    }
}
