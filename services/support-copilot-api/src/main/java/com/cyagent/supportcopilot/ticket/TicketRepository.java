package com.cyagent.supportcopilot.ticket;

import java.util.Optional;

import jakarta.persistence.LockModeType;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface TicketRepository extends JpaRepository<Ticket, String> {

	boolean existsByTicketNo(String ticketNo);

	@Lock(LockModeType.PESSIMISTIC_WRITE)
	@Query("select ticket from Ticket ticket where ticket.id = :id")
	Optional<Ticket> findByIdForUpdate(@Param("id") String id);
}
