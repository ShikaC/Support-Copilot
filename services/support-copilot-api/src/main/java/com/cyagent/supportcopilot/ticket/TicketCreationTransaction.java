package com.cyagent.supportcopilot.ticket;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.cyagent.supportcopilot.idempotency.CommandIdempotencyCompletion;
import com.cyagent.supportcopilot.idempotency.CommandOwnership;

@Service
public class TicketCreationTransaction {
    private final TicketService tickets;
    private final CommandIdempotencyCompletion completion;
    public TicketCreationTransaction(TicketService tickets, CommandIdempotencyCompletion completion) {
        this.tickets = tickets;
        this.completion = completion;
    }
    @Transactional
    public TicketDtos.TicketResponse create(TicketDtos.CreateTicketRequest request, CommandOwnership ownership) {
        var response = tickets.create(request);
        completion.complete(ownership, 201, response);
        return response;
    }
}
