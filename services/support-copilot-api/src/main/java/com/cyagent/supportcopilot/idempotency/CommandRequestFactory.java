package com.cyagent.supportcopilot.idempotency;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;

import com.cyagent.supportcopilot.identity.TrustedActorProvider;
import com.cyagent.supportcopilot.knowledge.KnowledgeScope;
import com.cyagent.supportcopilot.knowledge.TrustedSupportScopeProvider;

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
	private final TrustedActorProvider actorProvider;
	private final TrustedSupportScopeProvider scopeProvider;

	public CommandRequestFactory(
		ObjectMapper objectMapper,
		TrustedActorProvider actorProvider,
		TrustedSupportScopeProvider scopeProvider
	) {
		this.objectMapper = objectMapper;
		this.actorProvider = actorProvider;
		this.scopeProvider = scopeProvider;
	}

	public CommandRequest creation(IdempotencyKey key, com.cyagent.supportcopilot.ticket.TicketDtos.CreateTicketRequest payload) {
		return request(key, CommandType.CREATE_TICKET, "POST:/api/tickets/commands/create", null, null,
			new String(serialize(payload), StandardCharsets.UTF_8));
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
		var actor = actorProvider.currentActor();
		var canonical = new CanonicalCommand(
			commandType.name(),
			routeScope,
			ticketId,
			analysisId,
			normalizedPayload,
			actor.type().name(),
			actor.subject(),
			KnowledgeScope.names(scopeProvider.currentScopes().stream().distinct().sorted().toList())
		);
		return new CommandRequest(key, commandType, routeScope, sha256(serialize(canonical)));
	}

	private byte[] serialize(Object command) {
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
		String normalizedPayload,
		String actorType,
		String actorSubject,
		List<String> supportScopes
	) {
	}
}
