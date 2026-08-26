package com.cyagent.supportcopilot.knowledge;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.Version;

@Entity
@Table(name = "knowledge_active_release")
public class KnowledgeActiveRelease {

	public static final String SINGLETON_ID = "active";

	@Id
	@Column(nullable = false, updatable = false, length = 16)
	private String id;

	@Column(nullable = false, length = 64)
	private String releaseId;

	@Version
	@Column(nullable = false)
	private long version;

	protected KnowledgeActiveRelease() {
	}

	public KnowledgeActiveRelease(String releaseId) {
		this.id = SINGLETON_ID;
		this.releaseId = releaseId;
	}

	public void activate(String nextReleaseId) {
		releaseId = nextReleaseId;
	}

	public String getId() { return id; }
	public String getReleaseId() { return releaseId; }
	public long getVersion() { return version; }
}
