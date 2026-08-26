package com.cyagent.supportcopilot.knowledge;

import java.time.Instant;

import jakarta.persistence.Access;
import jakarta.persistence.AccessType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.Version;

import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "knowledge_releases")
@Access(AccessType.FIELD)
public class KnowledgeRelease {

	@Id
	@Column(nullable = false, updatable = false, length = 64)
	private String releaseId;

	@Column(nullable = false, updatable = false, unique = true)
	private int releaseVersion;

	@JdbcTypeCode(SqlTypes.CHAR)
	@Column(nullable = false, updatable = false, length = 64)
	private String corpusChecksum;

	@JdbcTypeCode(SqlTypes.VARCHAR)
	@Column(nullable = false, updatable = false, length = 256)
	private String allowedScopesJson;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 16)
	private KnowledgeReleaseStatus status;

	@Column(nullable = false, updatable = false, length = 128)
	private String createdBy;

	@Column(nullable = false, updatable = false)
	private Instant createdAt;

	@Column(length = 128)
	private String approvedBy;

	@Column
	private Instant approvedAt;

	@Column(length = 128)
	private String publishedBy;

	@Column
	private Instant publishedAt;

	@Version
	@Column(nullable = false)
	private long version;

	protected KnowledgeRelease() {
	}

	public KnowledgeRelease(
		String releaseId,
		int releaseVersion,
		String corpusChecksum,
		String allowedScopesJson,
		String createdBy,
		Instant createdAt
	) {
		this.releaseId = releaseId;
		this.releaseVersion = releaseVersion;
		this.corpusChecksum = corpusChecksum;
		this.allowedScopesJson = allowedScopesJson;
		this.status = KnowledgeReleaseStatus.DRAFT;
		this.createdBy = createdBy;
		this.createdAt = createdAt;
	}

	public void approve(String actor, Instant now) {
		status = KnowledgeReleaseStatus.APPROVED;
		approvedBy = actor;
		approvedAt = now;
	}

	public void publish(String actor, Instant now) {
		status = KnowledgeReleaseStatus.PUBLISHED;
		publishedBy = actor;
		publishedAt = now;
	}

	public void archive() {
		status = KnowledgeReleaseStatus.ARCHIVED;
	}

	public String getReleaseId() { return releaseId; }
	public int getReleaseVersion() { return releaseVersion; }
	public String getCorpusChecksum() { return corpusChecksum; }
	public String getAllowedScopesJson() { return allowedScopesJson; }
	public KnowledgeReleaseStatus getStatus() { return status; }
	public String getCreatedBy() { return createdBy; }
	public Instant getCreatedAt() { return createdAt; }
	public String getApprovedBy() { return approvedBy; }
	public Instant getApprovedAt() { return approvedAt; }
	public String getPublishedBy() { return publishedBy; }
	public Instant getPublishedAt() { return publishedAt; }
	public long getVersion() { return version; }
}
