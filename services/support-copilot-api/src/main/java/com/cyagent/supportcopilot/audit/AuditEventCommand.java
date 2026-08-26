package com.cyagent.supportcopilot.audit;

public record AuditEventCommand(
	AuditAction action,
	AuditTargetType targetType,
	String targetId,
	Long targetVersion,
	AuditMetadata metadata
) {

	public AuditEventCommand {
		if (action == null || targetType == null || metadata == null) {
			throw new IllegalArgumentException("Audit action, target type, and metadata are required.");
		}
		if (targetId == null || !targetId.matches("[A-Za-z0-9][A-Za-z0-9._:-]{0,254}")) {
			throw new IllegalArgumentException("Audit target id is invalid.");
		}
	}
}
