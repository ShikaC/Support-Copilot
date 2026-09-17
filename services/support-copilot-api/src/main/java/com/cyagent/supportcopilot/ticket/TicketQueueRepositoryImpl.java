package com.cyagent.supportcopilot.ticket;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

import jakarta.persistence.EntityManager;
import jakarta.persistence.criteria.CriteriaBuilder;
import jakarta.persistence.criteria.Expression;
import jakarta.persistence.criteria.Order;
import jakarta.persistence.criteria.Predicate;
import jakarta.persistence.criteria.Root;

public class TicketQueueRepositoryImpl implements TicketQueueRepository {
	private final EntityManager entityManager;

	public TicketQueueRepositoryImpl(EntityManager entityManager) {
		this.entityManager = entityManager;
	}

	@Override
	public List<Ticket> findQueuePage(TicketQueueQuery filters, TicketQueueCursor cursor, int limit) {
		var builder = entityManager.getCriteriaBuilder();
		var query = builder.createQuery(Ticket.class);
		var ticket = query.from(Ticket.class);
		var predicates = filters(builder, ticket, filters);
		if (cursor != null) predicates.add(after(builder, ticket, filters.sort(), cursor));
		query.select(ticket).where(predicates.toArray(Predicate[]::new))
			.orderBy(order(builder, ticket, filters.sort()));
		return entityManager.createQuery(query).setMaxResults(limit).getResultList();
	}

	@Override
	public long countQueue(TicketQueueQuery filters) {
		var builder = entityManager.getCriteriaBuilder();
		var query = builder.createQuery(Long.class);
		var ticket = query.from(Ticket.class);
		query.select(builder.count(ticket)).where(filters(builder, ticket, filters).toArray(Predicate[]::new));
		return entityManager.createQuery(query).getSingleResult();
	}

	private List<Predicate> filters(CriteriaBuilder builder, Root<Ticket> ticket, TicketQueueQuery filters) {
		var predicates = new ArrayList<Predicate>();
		if (!filters.statuses().isEmpty()) predicates.add(ticket.get("status").in(filters.statuses()));
		if (!filters.priorities().isEmpty()) predicates.add(ticket.get("priority").in(filters.priorities()));
		if (!filters.categories().isEmpty()) predicates.add(ticket.get("category").in(filters.categories()));
		if (!filters.assignee().isEmpty()) {
			predicates.add(filters.assignee().equals("UNASSIGNED")
				? builder.isNull(ticket.get("assigneeName"))
				: builder.equal(ticket.get("assigneeName"), filters.assignee()));
		}
		if (!filters.keyword().isEmpty()) {
			var pattern = "%" + filters.keyword().replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%";
			var matches = List.of("ticketNo", "subject", "description", "customerName", "customerCompany").stream()
				.map(field -> builder.like(builder.lower(ticket.get(field)), pattern, '!')).toArray(Predicate[]::new);
			predicates.add(builder.or(matches));
		}
		return predicates;
	}

	private List<Order> order(CriteriaBuilder builder, Root<Ticket> ticket, TicketQueueQuery.Sort sort) {
		var newest = List.of(builder.desc(ticket.get("createdAt")), builder.desc(ticket.get("id")));
		return switch (sort) {
			case NEWEST -> newest;
			case SLA -> List.of(builder.asc(ticket.get("slaDeadline")), newest.get(0), newest.get(1));
			case PRIORITY -> List.of(builder.desc(priorityRank(builder, ticket)), newest.get(0), newest.get(1));
		};
	}

	private Predicate after(CriteriaBuilder builder, Root<Ticket> ticket, TicketQueueQuery.Sort sort, TicketQueueCursor cursor) {
		var older = builder.or(builder.lessThan(ticket.<Instant>get("createdAt"), cursor.createdAt()),
			builder.and(builder.equal(ticket.get("createdAt"), cursor.createdAt()),
				builder.lessThan(ticket.<String>get("id"), cursor.id())));
		return switch (sort) {
			case NEWEST -> older;
			case SLA -> builder.or(builder.greaterThan(ticket.<Instant>get("slaDeadline"), cursor.slaDeadline()),
				builder.and(builder.equal(ticket.get("slaDeadline"), cursor.slaDeadline()), older));
			case PRIORITY -> builder.or(builder.lessThan(priorityRank(builder, ticket), rank(cursor.priority())),
				builder.and(builder.equal(priorityRank(builder, ticket), rank(cursor.priority())), older));
		};
	}

	private Expression<Integer> priorityRank(CriteriaBuilder builder, Root<Ticket> ticket) {
		return builder.<String, Integer>selectCase(ticket.get("priority"))
			.when("URGENT", 4).when("HIGH", 3).when("MEDIUM", 2).otherwise(1);
	}

	private int rank(String priority) {
		return switch (TicketDomain.parsePriority(priority)) {
			case URGENT -> 4;
			case HIGH -> 3;
			case MEDIUM -> 2;
			case LOW -> 1;
		};
	}
}
