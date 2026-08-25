package com.cyagent.supportcopilot.analysis;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

public enum FallbackReason {
	INSUFFICIENT_EVIDENCE("insufficient_evidence"),
	EMBEDDING_API_ERROR("embedding_api_error"),
	EMBEDDING_CONNECTION_TIMEOUT("embedding_connection_timeout"),
	EMBEDDING_RESPONSE_TIMEOUT("embedding_response_timeout"),
	STRUCTURED_GENERATION_API_ERROR("structured_generation_api_error"),
	STRUCTURED_GENERATION_CONNECTION_TIMEOUT("structured_generation_connection_timeout"),
	STRUCTURED_GENERATION_RESPONSE_TIMEOUT("structured_generation_response_timeout"),
	INVALID_MODEL_RESPONSE("invalid_model_response"),
	PROCESSING_TIMEOUT("processing_timeout"),
	AI_SERVICE_TIMEOUT("ai_service_timeout"),
	AI_SERVICE_UNAVAILABLE("ai_service_unavailable"),
	AI_SERVICE_ERROR("ai_service_error"),
	INVALID_AI_RESPONSE("invalid_ai_response");

	private final String value;

	FallbackReason(String value) {
		this.value = value;
	}

	@JsonValue
	public String value() {
		return value;
	}

	@JsonCreator
	public static FallbackReason fromValue(String value) {
		for (var reason : values()) {
			if (reason.value.equals(value)) {
				return reason;
			}
		}
		throw new IllegalArgumentException("Unknown fallback reason: " + value);
	}
}
