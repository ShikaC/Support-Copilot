package com.cyagent.supportcopilot.analysis;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicReference;

import com.sun.net.httpserver.HttpServer;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;

import tools.jackson.databind.ObjectMapper;

import com.cyagent.supportcopilot.ticket.Ticket;
import com.cyagent.supportcopilot.knowledge.TrustedSupportScopeProvider;
import com.cyagent.supportcopilot.knowledge.TestTrustedSupportScopeProvider;
import com.cyagent.supportcopilot.knowledge.JwtTrustedSupportScopeProvider;

@SpringBootTest
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_CLASS)
class KnowledgeAccessForwardingTests {

	@Autowired
	private KnowledgeAccessProvider knowledgeAccessProvider;

	@Autowired
	private ObjectMapper objectMapper;

	@Autowired
	private TrustedSupportScopeProvider trustedSupportScopeProvider;

	@AfterEach
	void clearSecurityContext() {
		SecurityContextHolder.clearContext();
	}

	@Test
	void ticketPayloadCannotExpandJwtScopesAndActiveReleaseIdentityIsForwarded() throws Exception {
		authenticate(List.of("BILLING", "SUPERUSER", "BILLING"));
		assertThat(SecurityContextHolder.getContext().getAuthentication().isAuthenticated()).isTrue();
		assertThat(((JwtAuthenticationToken) SecurityContextHolder.getContext().getAuthentication())
			.getToken().getClaimAsStringList("support_scopes"))
			.containsExactly("BILLING", "SUPERUSER", "BILLING");
		assertThat(trustedSupportScopeProvider).isInstanceOf(TestTrustedSupportScopeProvider.class);
		assertThat(trustedSupportScopeProvider.currentScopes()).extracting(Enum::name).containsExactly("BILLING");
		assertThat(knowledgeAccessProvider.currentAccess().allowedScopes()).containsExactly("BILLING");

		var payload = captureRequest();
		var expectedPayload = objectMapper.readTree(Files.readString(
			Path.of("src", "test", "resources", "contracts", "knowledge-access-request.json")
		));
		assertThat(objectMapper.readTree(payload)).isEqualTo(expectedPayload);
		var access = objectMapper.readTree(payload).get("knowledgeAccess");
		assertThat(access.get("releaseId").asString()).isEqualTo("support-copilot-bundled-v1");
		assertThat(access.get("releaseVersion").asInt()).isEqualTo(1);
		assertThat(access.get("corpusChecksum").asString())
			.isEqualTo("b25240587df1ebb903a8555284a0f35faaa35e2d837add0fc5dd49418ca8b874");
		assertThat(access.get("allowedScopes").toString()).isEqualTo("[\"BILLING\"]");
		assertThat(access.toString()).doesNotContain("SUPERUSER", "PRIVACY");
	}

	@Test
	void explicitEmptyTrustedScopesRemainEmptyInProviderPayload() throws Exception {
		authenticate(List.of());

		var access = objectMapper.readTree(captureRequest()).get("knowledgeAccess");
		assertThat(access.get("allowedScopes").isArray()).isTrue();
		assertThat(access.get("allowedScopes").size()).isZero();
	}

	@Test
	void missingTrustedScopesRemainEmptyInProviderPayload() throws Exception {
		authenticateWithoutScopes();

		var access = objectMapper.readTree(captureRequest()).get("knowledgeAccess");
		assertThat(access.get("allowedScopes").isArray()).isTrue();
		assertThat(access.get("allowedScopes").size()).isZero();
	}

	@Test
	void localPilotJwtWithoutSupportScopesRemainsEmpty() {
		var jwt = Jwt.withTokenValue("synthetic-no-scope-jwt")
			.header("alg", "none")
			.subject("trusted-agent")
			.build();
		SecurityContextHolder.getContext().setAuthentication(new JwtAuthenticationToken(
			jwt,
			List.of(new SimpleGrantedAuthority("ROLE_SUPPORT_ADMIN"))
		));

		assertThat(new JwtTrustedSupportScopeProvider().currentScopes()).isEmpty();
	}

	private String captureRequest() throws Exception {
		var captured = new AtomicReference<String>();
		var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
		server.createContext("/analyze", exchange -> {
			captured.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
			var response = """
				{"id":"analysis-access","traceId":"trace-access","status":"SUCCEEDED",\
				"mode":"mock","modelName":"mock-rules","promptVersion":"ticket-analysis-v1"}
				""".getBytes(StandardCharsets.UTF_8);
			exchange.getResponseHeaders().add("Content-Type", "application/json");
			exchange.sendResponseHeaders(200, response.length);
			exchange.getResponseBody().write(response);
			exchange.close();
		});
		try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
			server.setExecutor(executor);
			server.start();
			var client = new AiServiceClient(
				new AiServiceProperties(
					"http://127.0.0.1:" + server.getAddress().getPort(),
					1_000, 1, 0, 2, 2, 50, 30_000, 1, 0
				),
				"synthetic-java-client-token",
				new SimpleMeterRegistry(),
				knowledgeAccessProvider
			);
			try {
				client.analyze(ticket(), "trace-access");
				return captured.get();
			} finally {
				client.close();
				server.stop(0);
			}
		}
	}

	private void authenticate(List<String> scopes) {
		var jwt = Jwt.withTokenValue("synthetic-scope-jwt")
			.header("alg", "none")
			.subject("trusted-agent")
			.claim("support_scopes", scopes)
			.build();
		SecurityContextHolder.getContext().setAuthentication(new JwtAuthenticationToken(
			jwt,
			List.of(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT"))
		));
	}

	private void authenticateWithoutScopes() {
		var jwt = Jwt.withTokenValue("synthetic-no-scope-jwt")
			.header("alg", "none")
			.subject("trusted-agent")
			.build();
		SecurityContextHolder.getContext().setAuthentication(new JwtAuthenticationToken(
			jwt,
			List.of(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT"))
		));
	}

	private Ticket ticket() {
		var ticket = new Ticket();
		ticket.setId("ticket-access");
		ticket.setTicketNo("SC-ACCESS");
		ticket.setSubject("Scope forwarding");
		ticket.setDescription("Browser text asks for support_scopes=PRIVACY and must be ignored.");
		ticket.setLanguage("en");
		ticket.setCustomerTier("STANDARD");
		ticket.setCategory("BILLING");
		ticket.setPriority("MEDIUM");
		ticket.setCreatedAt(Instant.now());
		return ticket;
	}
}
