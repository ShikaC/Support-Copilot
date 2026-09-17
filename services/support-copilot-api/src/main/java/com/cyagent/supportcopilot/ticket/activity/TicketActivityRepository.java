package com.cyagent.supportcopilot.ticket.activity;

import java.util.List;

import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import org.springframework.stereotype.Repository;

import com.cyagent.supportcopilot.audit.AuditEvent;

@Repository
class TicketActivityRepository {
    @PersistenceContext
    private EntityManager entityManager;

    List<AuditEvent> list(String ticketId, TicketActivityService.Cursor cursor, int limit) {
        var cursorCondition = cursor == null ? "" : """
            and (event.createdAt < :beforeTime or
                (event.createdAt = :beforeTime and event.id < :beforeId))
            """;
        var query = entityManager.createQuery("""
            select event from AuditEvent event where (
                (event.targetType = 'TICKET' and event.targetId = :ticketId
                    and event.action in ('TICKET_CREATED', 'TICKET_UPDATED', 'TICKET_UNASSIGNED', 'TICKET_NOTE_ADDED'))
                or (event.targetType = 'ANALYSIS' and event.action = 'ANALYSIS_PERSISTED'
                    and exists (select run.id from AnalysisRun run
                        where run.id = event.targetId and run.ticketId = :ticketId))
                or (event.targetType = 'ANALYSIS_REVIEW'
                    and event.action in ('ANALYSIS_REVIEW_APPROVED', 'ANALYSIS_REVIEW_EDITED', 'ANALYSIS_REVIEW_REJECTED')
                    and exists (select review.id from AnalysisReview review
                        where review.id = event.targetId and review.ticketId = :ticketId))
                )
            """ + cursorCondition + " order by event.createdAt desc, event.id desc", AuditEvent.class)
            .setParameter("ticketId", ticketId).setMaxResults(limit);
        if (cursor != null) {
            query.setParameter("beforeTime", cursor.createdAt());
            query.setParameter("beforeId", cursor.id());
        }
        return List.copyOf(query.getResultList());
    }
}
