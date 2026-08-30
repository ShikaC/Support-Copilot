package com.cyagent.supportcopilot.ticket;

import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.Set;

import jakarta.persistence.LockModeType;

import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface TicketRepository extends JpaRepository<Ticket, String> {

	boolean existsByTicketNo(String ticketNo);

	@Query("""
		select ticket from Ticket ticket
		where (:statusEnabled = false or ticket.status in :statuses)
		  and (:priorityEnabled = false or ticket.priority in :priorities)
		  and (:categoryEnabled = false or ticket.category in :categories)
		  and (
			:keyword = ''
			or lower(ticket.ticketNo) like concat('%', :keyword, '%') escape '!'
			or lower(ticket.subject) like concat('%', :keyword, '%') escape '!'
			or lower(ticket.customerName) like concat('%', :keyword, '%') escape '!'
			or lower(ticket.customerCompany) like concat('%', :keyword, '%') escape '!'
		  )
		order by ticket.createdAt desc, ticket.id desc
		""")
	List<Ticket> findFirstPage(
		@Param("statuses") Set<String> statuses,
		@Param("statusEnabled") boolean statusEnabled,
		@Param("priorities") Set<String> priorities,
		@Param("priorityEnabled") boolean priorityEnabled,
		@Param("categories") Set<String> categories,
		@Param("categoryEnabled") boolean categoryEnabled,
		@Param("keyword") String keyword,
		Pageable pageable
	);

	@Query("""
		select ticket from Ticket ticket
		where (:statusEnabled = false or ticket.status in :statuses)
		  and (:priorityEnabled = false or ticket.priority in :priorities)
		  and (:categoryEnabled = false or ticket.category in :categories)
		  and (
			:keyword = ''
			or lower(ticket.ticketNo) like concat('%', :keyword, '%') escape '!'
			or lower(ticket.subject) like concat('%', :keyword, '%') escape '!'
			or lower(ticket.customerName) like concat('%', :keyword, '%') escape '!'
			or lower(ticket.customerCompany) like concat('%', :keyword, '%') escape '!'
		  )
		  and (
			ticket.createdAt < :cursorCreatedAt
			or (ticket.createdAt = :cursorCreatedAt and ticket.id < :cursorId)
		  )
		order by ticket.createdAt desc, ticket.id desc
		""")
	List<Ticket> findPageAfter(
		@Param("statuses") Set<String> statuses,
		@Param("statusEnabled") boolean statusEnabled,
		@Param("priorities") Set<String> priorities,
		@Param("priorityEnabled") boolean priorityEnabled,
		@Param("categories") Set<String> categories,
		@Param("categoryEnabled") boolean categoryEnabled,
		@Param("keyword") String keyword,
		@Param("cursorCreatedAt") Instant cursorCreatedAt,
		@Param("cursorId") String cursorId,
		Pageable pageable
	);

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
