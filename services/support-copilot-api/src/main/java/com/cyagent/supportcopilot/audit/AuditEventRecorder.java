package com.cyagent.supportcopilot.audit;

import java.time.Instant;
import java.util.UUID;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import com.cyagent.supportcopilot.common.TraceId;
import com.cyagent.supportcopilot.identity.TrustedActorProvider;

@Service
public class AuditEventRecorder {

	private final AuditEventRepository auditEventRepository;
	private final TrustedActorProvider trustedActorProvider;
	private final ObjectMapper objectMapper;

	public AuditEventRecorder(
		AuditEventRepository auditEventRepository,
		TrustedActorProvider trustedActorProvider,
		ObjectMapper objectMapper
	) {
		this.auditEventRepository = auditEventRepository;
		this.trustedActorProvider = trustedActorProvider;
		this.objectMapper = objectMapper;
	}

	@Transactional(propagation = Propagation.MANDATORY)
	public void record(AuditEventCommand command) {
		requireAllowedMetadata(command);
		var actor = trustedActorProvider.currentActor();
		auditEventRepository.insert(new AuditEvent(
			"audit-" + UUID.randomUUID(),
			actor.subject(),
			actor.type().name(),
			serialize(actor.roles()),
			command.action().name(),
			command.targetType().name(),
			command.targetId(),
			command.targetVersion(),
			TraceId.currentOrCreate(),
			serialize(command.metadata()),
			Instant.now()
		));
	}

	private void requireAllowedMetadata(AuditEventCommand command) {
		var valid = switch (command.action()) {
			case TICKET_CREATED -> command.metadata() instanceof AuditMetadata.None;
			case TICKET_UPDATED, TICKET_UNASSIGNED ->
				command.metadata() instanceof AuditMetadata.TicketChange;
			case ANALYSIS_PERSISTED -> command.metadata() instanceof AuditMetadata.Analysis;
			case ANALYSIS_REVIEW_APPROVED, ANALYSIS_REVIEW_EDITED, ANALYSIS_REVIEW_REJECTED ->
				command.metadata() instanceof AuditMetadata.Review;
			case KNOWLEDGE_RELEASE_DRAFT_CREATED, KNOWLEDGE_RELEASE_APPROVED,
				KNOWLEDGE_RELEASE_PUBLISHED, KNOWLEDGE_RELEASE_ROLLED_BACK ->
				command.metadata() instanceof AuditMetadata.KnowledgeRelease;
		};
		if (!valid) {
			throw new IllegalArgumentException("Audit metadata does not match the controlled action.");
		}
	}

	private String serialize(Object value) {
		try {
			return objectMapper.writeValueAsString(value);
		} catch (JacksonException exception) {
			throw new IllegalStateException("Unable to serialize allowlisted audit data.", exception);
		}
	}
}
