package com.cyagent.supportcopilot.knowledge;

import java.time.Instant;
import java.util.List;

public final class KnowledgeReleaseDtos {

	private KnowledgeReleaseDtos() {
	}

	public record CreateReleaseRequest(
		String releaseId,
		int releaseVersion,
		String corpusChecksum,
		List<String> allowedScopes
	) {
	}

	public record TransitionRequest(long expectedVersion) {
	}

	public record ReleaseResponse(
		String releaseId,
		int releaseVersion,
		String corpusChecksum,
		List<String> allowedScopes,
		KnowledgeReleaseStatus status,
		String createdBy,
		Instant createdAt,
		String approvedBy,
		Instant approvedAt,
		String publishedBy,
		Instant publishedAt,
		long version
	) {
	}
}
