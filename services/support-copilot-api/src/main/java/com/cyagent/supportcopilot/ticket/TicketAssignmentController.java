package com.cyagent.supportcopilot.ticket;

import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;
import com.cyagent.supportcopilot.identity.TrustedActorProvider;

@RestController
@RequestMapping("/api/tickets/{ticketId}/claim")
public class TicketAssignmentController {
    private final TicketService tickets;
    private final TrustedActorProvider actors;
    public TicketAssignmentController(TicketService tickets, TrustedActorProvider actors) {
        this.tickets = tickets;
        this.actors = actors;
    }
    @PostMapping
    public TicketDtos.TicketResponse claim(@PathVariable String ticketId,
        @Valid @RequestBody TicketDtos.UnassignTicketRequest request) {
        var ticket = tickets.get(ticketId);
        if ("CLOSED".equals(ticket.status()) || "RESOLVED".equals(ticket.status())) {
            throw new TicketStateConflictException(ticketId, ticket.status());
        }
        var actor = actors.currentActor();
        var label = actor.displayLabel();
        return tickets.update(ticketId, new TicketDtos.UpdateTicketRequest(null, null, null,
            label.substring(0, Math.min(label.length(), 80)), request.expectedVersion()));
    }
}
