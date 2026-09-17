package com.cyagent.supportcopilot.ticket;

import java.time.Instant;
import java.util.List;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/tickets/{ticketId}/notes")
public class TicketNoteController {
    private final TicketNoteService service;
    public TicketNoteController(TicketNoteService service) { this.service = service; }

    @GetMapping
    public List<NoteResponse> list(@PathVariable String ticketId) { return service.list(ticketId); }

    @PostMapping
    public NoteResponse add(@PathVariable String ticketId, @Valid @RequestBody CreateNoteRequest request) {
        return service.add(ticketId, request);
    }

    public record CreateNoteRequest(
        @NotBlank @Pattern(regexp = "[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}") String noteId,
        @NotBlank @Size(max = 4000) String content,
        @NotNull @PositiveOrZero Long expectedVersion
    ) {}

    public record NoteResponse(String id, String ticketId, String content, String authorLabel, Instant createdAt) {
        static NoteResponse from(TicketNote note) {
            return new NoteResponse(note.getId(), note.getTicketId(), note.getContent(), note.getAuthorLabel(), note.getCreatedAt());
        }
    }
}
