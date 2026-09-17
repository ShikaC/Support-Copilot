package com.cyagent.supportcopilot.ticket;

import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import com.cyagent.supportcopilot.idempotency.CommandIdempotencyCoordinator;
import com.cyagent.supportcopilot.idempotency.CommandRequestFactory;
import com.cyagent.supportcopilot.idempotency.IdempotencyKey;

@RestController
@RequestMapping("/api/tickets/commands/create")
public class TicketCreationController {
    private final TicketCreationTransaction creation;
    private final CommandIdempotencyCoordinator coordinator;
    private final CommandRequestFactory requests;
    public TicketCreationController(TicketCreationTransaction creation, CommandIdempotencyCoordinator coordinator, CommandRequestFactory requests) {
        this.creation = creation;
        this.coordinator = coordinator;
        this.requests = requests;
    }
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public TicketDtos.TicketResponse create(@Valid @RequestBody TicketDtos.CreateTicketRequest request,
        @RequestHeader(name = "Idempotency-Key", required = false) String rawKey) {
        var command = requests.creation(IdempotencyKey.parse(rawKey), request);
        return coordinator.execute(command, TicketDtos.TicketResponse.class,
            ownership -> creation.create(request, ownership));
    }
}
