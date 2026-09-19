package com.cyagent.supportcopilot.idempotency;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

import com.cyagent.supportcopilot.ticket.TicketDtos.CreateTicketRequest;
import com.cyagent.supportcopilot.ticket.TicketDomain.Channel;
import com.cyagent.supportcopilot.ticket.TicketDomain.CustomerTier;
import com.cyagent.supportcopilot.identity.JwtTrustedActorProvider;
import com.cyagent.supportcopilot.identity.TrustedActorProvider.TrustedActor;
import com.cyagent.supportcopilot.identity.TrustedActorProvider.TrustedActorType;
import com.cyagent.supportcopilot.knowledge.KnowledgeScope;
import com.cyagent.supportcopilot.knowledge.TestTrustedSupportScopeProvider;

import tools.jackson.databind.ObjectMapper;

class CommandRequestFactoryTests {

	private final CommandRequestFactory factory = new CommandRequestFactory(
		new ObjectMapper(), new JwtTrustedActorProvider(), new TestTrustedSupportScopeProvider()
	);

	@AfterEach
	void clearAuthentication() {
		SecurityContextHolder.clearContext();
	}

	@ParameterizedTest
	@EnumSource(CommandType.class)
	void anotherActorCannotMatchTheOriginalCommand(CommandType type) {
		authenticate("original-agent", List.of("BILLING"));
		var original = request(type);

		authenticate("another-agent", List.of("BILLING"));
		var anotherActor = request(type);

		assertThat(anotherActor.requestFingerprint()).isNotEqualTo(original.requestFingerprint());
	}

	@ParameterizedTest
	@EnumSource(CommandType.class)
	void reducedScopesCannotMatchTheOriginalCommand(CommandType type) {
		authenticate("same-agent", List.of("GENERAL", "BILLING"));
		var original = request(type);

		authenticate("same-agent", List.of("GENERAL"));
		var reducedAccess = request(type);

		assertThat(reducedAccess.requestFingerprint()).isNotEqualTo(original.requestFingerprint());
	}

	@ParameterizedTest
	@EnumSource(CommandType.class)
	void equivalentScopesPreserveTheOriginalCommand(CommandType type) {
		authenticate("same-agent", List.of("GENERAL", "BILLING"));
		var original = request(type);

		authenticate("same-agent", List.of("BILLING", "GENERAL", "BILLING"));
		var reorderedScopes = request(type);

		assertThat(reorderedScopes.requestFingerprint()).isEqualTo(original.requestFingerprint());
	}

	@org.junit.jupiter.api.Test
	void authenticatedAndDemoActorsWithTheSameSubjectRemainDistinct() {
		var authenticated = new CommandRequestFactory(new ObjectMapper(),
			() -> new TrustedActor("same-subject", TrustedActorType.AUTHENTICATED_JWT, List.of(), "same"),
			() -> List.of(KnowledgeScope.BILLING));
		var demo = new CommandRequestFactory(new ObjectMapper(),
			() -> new TrustedActor("same-subject", TrustedActorType.UNAUTHENTICATED_DEMO, List.of(), "same"),
			() -> List.of(KnowledgeScope.BILLING));
		var key = IdempotencyKey.parse("actor-type-command-0001");

		assertThat(demo.analysis(key, "ticket-1").requestFingerprint())
			.isNotEqualTo(authenticated.analysis(key, "ticket-1").requestFingerprint());
	}

	private CommandRequest request(CommandType type) {
		var key = IdempotencyKey.parse("caller-bound-command-0001");
		return switch (type) {
			case CREATE_TICKET -> factory.creation(key, new CreateTicketRequest(
				Channel.EMAIL, "Synthetic customer", "Synthetic company", CustomerTier.STANDARD,
				"Synthetic subject", "Synthetic description", "en"
			));
			case ANALYZE_TICKET -> factory.analysis(key, "ticket-caller-bound");
			case REVIEW_ANALYSIS -> factory.review(key, "ticket-caller-bound", "analysis-1", "Reviewed reply");
			case REJECT_ANALYSIS -> factory.reject(key, "ticket-caller-bound", "analysis-1", "Review rejected");
		};
	}

	private void authenticate(String subject, List<String> scopes) {
		var jwt = Jwt.withTokenValue("synthetic-command-scope-jwt")
			.header("alg", "none")
			.subject(subject)
			.claim("support_scopes", scopes)
			.build();
		SecurityContextHolder.getContext().setAuthentication(new JwtAuthenticationToken(
			jwt, List.of(new SimpleGrantedAuthority("ROLE_SUPPORT_REVIEWER"))
		));
	}
}
