package com.cyagent.supportcopilot.analysis;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.Executors;

import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import com.cyagent.supportcopilot.ticket.Ticket;

class AiServiceClientTests {

	@Test
	void pythonAuthenticationFailureIsNotConvertedToFallback() throws Exception {
		// Given: Python rejects Java's configured internal credential.
		var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
		server.createContext("/analyze", exchange -> {
			exchange.sendResponseHeaders(401, -1);
			exchange.close();
		});
		try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
			server.setExecutor(executor);
			server.start();
			var client = new AiServiceClient(
				"http://127.0.0.1:" + server.getAddress().getPort(),
				1_000,
				"synthetic-mismatched-token"
			);

			try {
				// When/Then: auth failure escapes the fallback exception boundary.
				assertThatThrownBy(() -> client.analyze(ticket(), "trace-auth-failure"))
					.isInstanceOf(IllegalStateException.class)
					.isNotInstanceOf(AiServiceCallException.class);
			} finally {
				server.stop(0);
			}
		}
	}

	@Test
	void pythonRequestValidationFailureIsNotConvertedToFallback() throws Exception {
		var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
		server.createContext("/analyze", exchange -> {
			exchange.sendResponseHeaders(422, -1);
			exchange.close();
		});
		try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
			server.setExecutor(executor);
			server.start();
			var client = new AiServiceClient(
				"http://127.0.0.1:" + server.getAddress().getPort(),
				1_000,
				"synthetic-java-client-token"
			);

			try {
				assertThatThrownBy(() -> client.analyze(ticket(), "trace-validation-failure"))
					.isInstanceOf(IllegalStateException.class)
					.isNotInstanceOf(AiServiceCallException.class);
			} finally {
				server.stop(0);
			}
		}
	}

	@Test
	void analyzeRequestSendsInternalCredentialAndPreservesJavaPythonShapeAndTrace() throws Exception {
		// Given: a real HTTP boundary captures the request Java currently sends to Python.
		var requestBody = new AtomicReference<String>();
		var traceHeader = new AtomicReference<String>();
		var internalTokenHeader = new AtomicReference<String>();
		var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
		server.createContext("/analyze", exchange -> {
			requestBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
			traceHeader.set(exchange.getRequestHeaders().getFirst("X-Trace-Id"));
			internalTokenHeader.set(exchange.getRequestHeaders().getFirst("X-Internal-Service-Token"));
			var body = """
				{"id":"analysis-shape","traceId":"trace-shape","status":"SUCCEEDED",\
				"mode":"mock","modelName":"mock-rules","promptVersion":"ticket-analysis-v1"}
				""".getBytes(StandardCharsets.UTF_8);
			exchange.getResponseHeaders().add("Content-Type", "application/json");
			exchange.sendResponseHeaders(200, body.length);
			exchange.getResponseBody().write(body);
			exchange.close();
		});
		try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
			server.setExecutor(executor);
			server.start();
			var client = new AiServiceClient(
				"http://127.0.0.1:" + server.getAddress().getPort(),
				1_000,
				"synthetic-java-client-token"
			);

			try {
				// When: Java makes its normal analysis request.
				client.analyze(ticket(), "trace-shape");

				// Then: the body contract and trace remain stable while the server-only credential is added.
				assertThat(requestBody.get())
					.contains("\"traceId\":\"trace-shape\"")
					.contains("\"id\":\"ticket-timeout\"")
					.contains("\"topN\":10")
					.contains("\"topK\":3")
					.contains("\"promptVersion\":\"ticket-analysis-v1\"");
				assertThat(traceHeader.get()).isEqualTo("trace-shape");
				assertThat(internalTokenHeader.get()).isEqualTo("synthetic-java-client-token");
			} finally {
				server.stop(0);
			}
		}
	}

	@Test
	void responseWithADifferentPolicyVersionIsRejected() throws Exception {
		// Given: Python returns a successful shape for a policy Java did not request.
		var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
		server.createContext("/analyze", exchange -> {
			var body = """
				{"id":"analysis-wrong-policy","traceId":"trace-policy","status":"SUCCEEDED",\
				"mode":"mock","modelName":"configured-chat-model","promptVersion":"ticket-analysis-v2"}
				""".getBytes(StandardCharsets.UTF_8);
			exchange.getResponseHeaders().add("Content-Type", "application/json");
			exchange.sendResponseHeaders(200, body.length);
			exchange.getResponseBody().write(body);
			exchange.close();
		});
		try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
			server.setExecutor(executor);
			server.start();
			var client = new AiServiceClient(
				"http://127.0.0.1:" + server.getAddress().getPort(),
				1_000,
				"synthetic-java-client-token"
			);

			try {
				// When/Then: Java refuses to persist a result under the wrong idempotency key.
				assertThatThrownBy(() -> client.analyze(ticket(), "trace-policy"))
					.isInstanceOfSatisfying(AiServiceCallException.class, exception ->
						assertThat(exception.getFallbackReason()).isEqualTo(FallbackReason.INVALID_AI_RESPONSE)
					);
			} finally {
				server.stop(0);
			}
		}
	}

	@Test
	void pythonProcessingTimeoutHasItsOwnFallbackReason() throws Exception {
		// Given: Python returns its structured overall-processing timeout response.
		var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
		server.createContext("/analyze", exchange -> {
			var body = """
				{"detail":{"code":"AI_PROCESSING_TIMEOUT","message":"deadline","traceId":"trace-python-timeout"}}
				""".getBytes(StandardCharsets.UTF_8);
			exchange.getResponseHeaders().add("Content-Type", "application/json");
			exchange.sendResponseHeaders(504, body.length);
			exchange.getResponseBody().write(body);
			exchange.close();
		});
		try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
			server.setExecutor(executor);
			server.start();
			var client = new AiServiceClient(
				"http://127.0.0.1:" + server.getAddress().getPort(),
				1_000,
				"synthetic-java-client-token"
			);

			try {
				// When/Then: Java preserves the Python deadline category for persistence.
				assertThatThrownBy(() -> client.analyze(ticket(), "trace-python-timeout"))
					.isInstanceOfSatisfying(AiServiceCallException.class, exception ->
						assertThat(exception.getFallbackReason()).isEqualTo(FallbackReason.PROCESSING_TIMEOUT)
					);
			} finally {
				server.stop(0);
			}
		}
	}

	@Test
	void slowPythonResponseStopsWithinTheConfiguredJavaBudget() throws Exception {
		// Given: a real HTTP endpoint accepts the request but responds too slowly.
		var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
		server.createContext("/analyze", exchange -> {
			try {
				Thread.sleep(1_000);
				exchange.sendResponseHeaders(503, -1);
			} catch (InterruptedException exception) {
				Thread.currentThread().interrupt();
			} finally {
				exchange.close();
			}
		});
		try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
			server.setExecutor(executor);
			server.start();
			var client = new AiServiceClient(
				"http://127.0.0.1:" + server.getAddress().getPort(),
				100,
				"synthetic-java-client-token"
			);
			var started = Instant.now();

			try {
				// When/Then: Java stops waiting inside its configured total budget.
					assertThatThrownBy(() -> client.analyze(ticket(), "trace-java-timeout"))
						.isInstanceOfSatisfying(AiServiceCallException.class, exception ->
							assertThat(exception.getFallbackReason()).isEqualTo(FallbackReason.AI_SERVICE_TIMEOUT)
						);
				assertThat(Duration.between(started, Instant.now())).isLessThan(Duration.ofMillis(800));
			} finally {
				server.stop(0);
			}
		}
	}

	private Ticket ticket() {
		var ticket = new Ticket();
		ticket.setId("ticket-timeout");
		ticket.setTicketNo("SC-TIMEOUT");
		ticket.setSubject("企业账号无法登录");
		ticket.setDescription("管理员和成员都无法进入工作区。");
		ticket.setLanguage("zh-CN");
		ticket.setCustomerTier("ENTERPRISE");
		ticket.setCategory("ACCOUNT_ACCESS");
		ticket.setPriority("HIGH");
		ticket.setCreatedAt(Instant.now());
		return ticket;
	}
}
