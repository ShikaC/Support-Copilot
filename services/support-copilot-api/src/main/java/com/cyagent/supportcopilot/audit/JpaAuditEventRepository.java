package com.cyagent.supportcopilot.audit;

import java.util.ArrayList;
import java.util.List;

import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;

import org.springframework.stereotype.Repository;

@Repository
class JpaAuditEventRepository implements AuditEventRepository {

	@PersistenceContext
	private EntityManager entityManager;

	@Override
	public void insert(AuditEvent event) {
		entityManager.persist(event);
		entityManager.flush();
	}

	@Override
	public List<AuditEvent> query(AuditEventQuery query) {
		var conditions = new ArrayList<String>();
		if (query.targetType() != null) {
			conditions.add("event.targetType = :targetType");
		}
		if (query.targetId() != null) {
			conditions.add("event.targetId = :targetId");
		}
		if (query.beforeCreatedAt() != null) {
			conditions.add("(event.createdAt < :beforeCreatedAt or "
				+ "(event.createdAt = :beforeCreatedAt and event.id < :beforeId))");
		}
		var where = conditions.isEmpty() ? "" : " where " + String.join(" and ", conditions);
		var result = entityManager.createQuery(
			"select event from AuditEvent event" + where + " order by event.createdAt desc, event.id desc",
			AuditEvent.class
		);
		if (query.targetType() != null) {
			result.setParameter("targetType", query.targetType().name());
		}
		if (query.targetId() != null) {
			result.setParameter("targetId", query.targetId());
		}
		if (query.beforeCreatedAt() != null) {
			result.setParameter("beforeCreatedAt", query.beforeCreatedAt());
			result.setParameter("beforeId", query.beforeId());
		}
		return List.copyOf(result.setMaxResults(query.limit()).getResultList());
	}
}
