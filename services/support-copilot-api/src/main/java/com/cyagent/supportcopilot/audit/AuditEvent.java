package com.cyagent.supportcopilot.audit;

import java.time.Instant;

import jakarta.persistence.Access;
import jakarta.persistence.AccessType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "audit_events")
@Access(AccessType.FIELD)
public class AuditEvent {

	@Id
	@Column(nullable = false, updatable = false, length = 64)
	private String id;

	@Column(nullable = false, updatable = false, length = 128)
	private String actorSubject;

	@Column(nullable = false, updatable = false, length = 32)
	private String actorType;

	@Column(nullable = false, updatable = false, length = 512)
	private String actorRolesJson;

	@Column(nullable = false, updatable = false, length = 64)
	private String action;

	@Column(nullable = false, updatable = false, length = 48)
	private String targetType;

	@Column(nullable = false, updatable = false, length = 255)
	private String targetId;

	@Column(updatable = false)
	private Long targetVersion;

	@Column(nullable = false, updatable = false, length = 64)
	private String traceId;

	@Column(nullable = false, updatable = false, columnDefinition = "LONGTEXT")
	private String metadataJson;

	@Column(nullable = false, updatable = false)
	private Instant createdAt;

	protected AuditEvent() {
	}

	public AuditEvent(
		String id,
		String actorSubject,
		String actorType,
		String actorRolesJson,
		String action,
		String targetType,
		String targetId,
		Long targetVersion,
		String traceId,
		String metadataJson,
		Instant createdAt
	) {
		this.id = id;
		this.actorSubject = actorSubject;
		this.actorType = actorType;
		this.actorRolesJson = actorRolesJson;
		this.action = action;
		this.targetType = targetType;
		this.targetId = targetId;
		this.targetVersion = targetVersion;
		this.traceId = traceId;
		this.metadataJson = metadataJson;
		this.createdAt = createdAt;
	}

	public String getId() { return id; }
	public String getActorSubject() { return actorSubject; }
	public String getActorType() { return actorType; }
	public String getActorRolesJson() { return actorRolesJson; }
	public String getAction() { return action; }
	public String getTargetType() { return targetType; }
	public String getTargetId() { return targetId; }
	public Long getTargetVersion() { return targetVersion; }
	public String getTraceId() { return traceId; }
	public String getMetadataJson() { return metadataJson; }
	public Instant getCreatedAt() { return createdAt; }
}
