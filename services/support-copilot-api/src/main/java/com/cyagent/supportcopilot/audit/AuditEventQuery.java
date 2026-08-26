package com.cyagent.supportcopilot.audit;

import java.time.Instant;

public record AuditEventQuery(
	AuditTargetType targetType,
	String targetId,
	Instant beforeCreatedAt,
	String beforeId,
	int limit
) {
}
