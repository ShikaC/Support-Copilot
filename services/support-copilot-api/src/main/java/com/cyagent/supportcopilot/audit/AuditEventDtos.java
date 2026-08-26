package com.cyagent.supportcopilot.audit;

import java.time.Instant;
import java.util.List;

import tools.jackson.databind.JsonNode;

public final class AuditEventDtos {

	private AuditEventDtos() {
	}

	public record AuditEventResponse(
		String id,
		String actorSubject,
		String actorType,
		List<String> actorRoles,
		AuditAction action,
		AuditTargetType targetType,
		String targetId,
		Long targetVersion,
		String traceId,
		Instant createdAt,
		JsonNode metadata
	) {
	}

	public record AuditEventPage(List<AuditEventResponse> items, String nextCursor) {
	}
}
