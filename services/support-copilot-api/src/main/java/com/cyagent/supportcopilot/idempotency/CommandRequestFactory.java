package com.cyagent.supportcopilot.idempotency;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

import org.springframework.stereotype.Component;

@Component
public class CommandRequestFactory {

	private static final String ANALYZE_ROUTE = "POST:/api/tickets/{ticketId}/analyze";
	private static final String REVIEW_ROUTE =
		"POST:/api/tickets/{ticketId}/analyses/{analysisId}/reviews";
	private static final String REJECT_ROUTE = REVIEW_ROUTE + "/reject";

	private final ObjectMapper objectMapper;

	public CommandRequestFactory(ObjectMapper objectMapper) {
		this.objectMapper = objectMapper;
	}

	public CommandRequest analysis(IdempotencyKey key, String ticketId) {
		return request(key, CommandType.ANALYZE_TICKET, ANALYZE_ROUTE, ticketId, null, null);
	}

	public CommandRequest review(IdempotencyKey key, String ticketId, String analysisId, String replyContent) {
		return request(
			key,
			CommandType.REVIEW_ANALYSIS,
			REVIEW_ROUTE,
			ticketId,
			analysisId,
			replyContent.trim()
		);
	}

	public CommandRequest reject(IdempotencyKey key, String ticketId, String analysisId, String reason) {
		return request(
			key,
			CommandType.REJECT_ANALYSIS,
			REJECT_ROUTE,
			ticketId,
			analysisId,
			reason.trim()
		);
	}

	private CommandRequest request(
		IdempotencyKey key,
		CommandType commandType,
		String routeScope,
		String ticketId,
		String analysisId,
		String normalizedPayload
	) {
		var canonical = new CanonicalCommand(
			commandType.name(),
			routeScope,
			ticketId,
			analysisId,
			normalizedPayload
		);
		return new CommandRequest(key, commandType, routeScope, sha256(serialize(canonical)));
	}

	private byte[] serialize(CanonicalCommand command) {
		try {
			return objectMapper.writeValueAsString(command).getBytes(StandardCharsets.UTF_8);
		} catch (JacksonException exception) {
			throw new IllegalStateException("Unable to fingerprint idempotent command", exception);
		}
	}

	private String sha256(byte[] value) {
		try {
			return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value));
		} catch (NoSuchAlgorithmException exception) {
			throw new IllegalStateException("SHA-256 is unavailable", exception);
		}
	}

	private record CanonicalCommand(
		String commandType,
		String routeScope,
		String ticketId,
		String analysisId,
		String normalizedPayload
	) {
	}
}
