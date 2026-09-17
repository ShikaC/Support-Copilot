package com.cyagent.supportcopilot.ticket;

import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TicketNoteRepository extends JpaRepository<TicketNote, String> {
    java.util.Optional<TicketNote> findByTicketIdAndRequestId(String ticketId, String requestId);
    List<TicketNote> findTop100ByTicketIdOrderByCreatedAtDescIdDesc(String ticketId);
}
