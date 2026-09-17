package com.cyagent.supportcopilot.ticket;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

import jakarta.persistence.LockModeType;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface TicketRepository extends JpaRepository<Ticket, String>, TicketQueueRepository {

	boolean existsByTicketNo(String ticketNo);

	long countByStatusNotIn(Collection<String> statuses);

	long countByPriority(String priority);

	@Query("""
		select ticket.category as category, count(ticket.id) as count
		from Ticket ticket
		group by ticket.category
		""")
	List<CategoryCountProjection> countByCategory();

	interface CategoryCountProjection {
		String getCategory();
		Long getCount();
	}

	@Lock(LockModeType.PESSIMISTIC_WRITE)
	@Query("select ticket from Ticket ticket where ticket.id = :id")
	Optional<Ticket> findByIdForUpdate(@Param("id") String id);
}
