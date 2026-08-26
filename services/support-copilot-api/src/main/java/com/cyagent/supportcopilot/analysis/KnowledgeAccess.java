package com.cyagent.supportcopilot.analysis;

import java.util.List;

public record KnowledgeAccess(
	String releaseId,
	int releaseVersion,
	String corpusChecksum,
	List<String> allowedScopes
) {
	public KnowledgeAccess {
		if (releaseId == null || releaseId.isBlank() || releaseVersion <= 0
			|| corpusChecksum == null || !corpusChecksum.matches("[a-f0-9]{64}")
			|| allowedScopes == null) {
			throw new IllegalArgumentException("Knowledge access contract is invalid.");
		}
		allowedScopes = List.copyOf(allowedScopes);
	}
}
