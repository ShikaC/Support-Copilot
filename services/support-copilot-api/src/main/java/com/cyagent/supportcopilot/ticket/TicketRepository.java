package com.cyagent.supportcopilot.ticket;

import org.springframework.data.jpa.repository.JpaRepository;

public interface TicketRepository extends JpaRepository<Ticket, String> {

	boolean existsByTicketNo(String ticketNo);
}
