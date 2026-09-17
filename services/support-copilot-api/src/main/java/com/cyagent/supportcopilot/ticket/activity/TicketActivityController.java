package com.cyagent.supportcopilot.ticket.activity;

import java.time.Instant;
import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.cyagent.supportcopilot.audit.AuditAction;

@RestController
@RequestMapping("/api/tickets/{ticketId}/activity")
public class TicketActivityController {
    private final TicketActivityService activity;

    public TicketActivityController(TicketActivityService activity) {
        this.activity = activity;
    }

    @GetMapping
    ActivityPage list(@PathVariable String ticketId,
        @RequestParam(required = false) String cursor,
        @RequestParam(defaultValue = "20") int limit) {
        return activity.list(ticketId, cursor, limit);
    }

    public record ActivityPage(List<ActivityItem> items, String nextCursor) {}

    public record ActivityItem(String id, AuditAction action, String actorLabel, Instant createdAt,
        String traceId, Long ticketVersion, String detail) {}
}
