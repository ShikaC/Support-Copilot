package com.cyagent.supportcopilot.ticket;

import java.time.Instant;
import java.util.List;
import jakarta.persistence.EntityNotFoundException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.cyagent.supportcopilot.analysis.TicketVersionConflictException;
import com.cyagent.supportcopilot.audit.*;
import com.cyagent.supportcopilot.identity.TrustedActorProvider;

@Service
public class TicketNoteService {
    private final TicketRepository tickets;
    private final TicketNoteRepository notes;
    private final TrustedActorProvider actors;
    private final AuditEventRecorder audit;

    public TicketNoteService(TicketRepository tickets, TicketNoteRepository notes, TrustedActorProvider actors, AuditEventRecorder audit) {
        this.tickets = tickets;
        this.notes = notes;
        this.actors = actors;
        this.audit = audit;
    }

    @Transactional(readOnly = true)
    public List<TicketNoteController.NoteResponse> list(String ticketId) {
        if (!tickets.existsById(ticketId)) throw new EntityNotFoundException("工单不存在：" + ticketId);
        return notes.findTop100ByTicketIdOrderByCreatedAtDescIdDesc(ticketId).stream()
            .map(TicketNoteController.NoteResponse::from).toList();
    }

    @Transactional
    public TicketNoteController.NoteResponse add(String ticketId, TicketNoteController.CreateNoteRequest request) {
        // Serialize note commands with the ticket; expectedVersion also protects concurrent ticket edits.
        var ticket = tickets.findByIdForUpdate(ticketId)
            .orElseThrow(() -> new EntityNotFoundException("工单不存在：" + ticketId));
        var actor = actors.currentActor();
        var existing = notes.findByTicketIdAndRequestId(ticketId, request.noteId());
        if (existing.isPresent()) {
            var note = existing.get();
            if (note.getTicketId().equals(ticketId) && note.getAuthorSubject().equals(actor.subject())
                && note.getContent().equals(request.content().trim())) return TicketNoteController.NoteResponse.from(note);
            throw new TicketVersionConflictException(ticketId, request.expectedVersion(), ticket.getVersion());
        }
        if (ticket.getVersion() != request.expectedVersion()) {
            throw new TicketVersionConflictException(ticketId, request.expectedVersion(), ticket.getVersion());
        }
        if ("CLOSED".equals(ticket.getStatus()) || "RESOLVED".equals(ticket.getStatus())) {
            throw new TicketStateConflictException(ticketId, ticket.getStatus());
        }
        var now = Instant.now();
        ticket.setUpdatedAt(now);
        tickets.saveAndFlush(ticket);
        var note = notes.saveAndFlush(new TicketNote(java.util.UUID.randomUUID().toString(), ticketId, request.noteId(), request.content().trim(),
            actor.subject(), actor.displayLabel(), now));
        audit.record(new AuditEventCommand(AuditAction.TICKET_NOTE_ADDED, AuditTargetType.TICKET,
            ticketId, ticket.getVersion(), new AuditMetadata.Note(note.getId())));
        return TicketNoteController.NoteResponse.from(note);
    }
}
