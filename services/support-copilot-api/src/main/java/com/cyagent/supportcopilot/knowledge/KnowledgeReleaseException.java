package com.cyagent.supportcopilot.knowledge;

import org.springframework.http.HttpStatus;

public class KnowledgeReleaseException extends RuntimeException {

	private final String code;
	private final HttpStatus status;

	private KnowledgeReleaseException(String code, HttpStatus status, String message) {
		super(message);
		this.code = code;
		this.status = status;
	}

	public static KnowledgeReleaseException notFound(String releaseId) {
		return new KnowledgeReleaseException(
			"KNOWLEDGE_RELEASE_NOT_FOUND",
			HttpStatus.NOT_FOUND,
			"Knowledge release was not found: " + releaseId
		);
	}

	public static KnowledgeReleaseException stale(String releaseId) {
		return new KnowledgeReleaseException(
			"KNOWLEDGE_RELEASE_VERSION_CONFLICT",
			HttpStatus.CONFLICT,
			"Knowledge release version is stale: " + releaseId
		);
	}

	public static KnowledgeReleaseException illegalTransition(String releaseId) {
		return new KnowledgeReleaseException(
			"KNOWLEDGE_RELEASE_ILLEGAL_TRANSITION",
			HttpStatus.CONFLICT,
			"Knowledge release transition is not allowed: " + releaseId
		);
	}

	public static KnowledgeReleaseException invalidChecksum() {
		return new KnowledgeReleaseException(
			"INVALID_KNOWLEDGE_CHECKSUM",
			HttpStatus.BAD_REQUEST,
			"Knowledge corpus checksum must be lowercase SHA-256."
		);
	}

	public static KnowledgeReleaseException invalidScope() {
		return new KnowledgeReleaseException(
			"INVALID_KNOWLEDGE_SCOPE",
			HttpStatus.BAD_REQUEST,
			"Knowledge scope is not allowlisted."
		);
	}

	public String code() {
		return code;
	}

	public HttpStatus status() {
		return status;
	}
}
