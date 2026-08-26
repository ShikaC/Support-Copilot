package com.cyagent.supportcopilot.analysis;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import com.sun.net.httpserver.HttpServer;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import com.cyagent.supportcopilot.ticket.Ticket;

class AiResilienceContractTests {

	private static final String INTERNAL_TOKEN = "synthetic-contract-token";
	private static final String SENSITIVE_CONTENT = "private-ticket-content-4111111111111111";

	@Test
	void boundedRateLimitRetryRecoversAndRecordsMetrics() throws Exception {
		var requests = new AtomicInteger();
		try (var server = server(exchange -> {
			if (requests.incrementAndGet() == 1) {
				exchange.sendResponseHeaders(429, -1);
				exchange.close();
				return;
			}
			respond(exchange, 200, successBody("trace-rate-limit", "live"));
		})) {
			var registry = new SimpleMeterRegistry();
			var client = client(server, registry, properties(server, 3, 2, 100, 1));

			var response = client.analyze(ticket(), "trace-rate-limit");

			assertThat(response.mode()).isEqualTo("live");
			assertThat(requests).hasValue(2);
			assertThat(counter(registry, "support.copilot.ai.boundary.attempts", "outcome", "transient_429"))
				.isEqualTo(1);
			assertThat(counter(registry, "support.copilot.ai.boundary.outcomes", "outcome", "success"))
				.isEqualTo(1);
		}
	}

	@Test
	void boundedServerErrorRetryRecovers() throws Exception {
		var requests = new AtomicInteger();
		try (var server = server(exchange -> {
			if (requests.incrementAndGet() == 1) {
				exchange.sendResponseHeaders(503, -1);
				exchange.close();
				return;
			}
			respond(exchange, 200, successBody("trace-server-error", "mock"));
		})) {
			var registry = new SimpleMeterRegistry();
			var client = client(server, registry, properties(server, 3, 2, 100, 1));

			assertThat(client.analyze(ticket(), "trace-server-error").mode()).isEqualTo("mock");
			assertThat(requests).hasValue(2);
			assertThat(counter(registry, "support.copilot.ai.boundary.attempts", "outcome", "transient_5xx"))
				.isEqualTo(1);
		}
	}

	@ParameterizedTest
	@ValueSource(ints = {400, 401, 403, 422})
	void clientAndAuthenticationFailuresAreNeverRetried(int status) throws Exception {
		var requests = new AtomicInteger();
		try (var server = server(exchange -> {
			requests.incrementAndGet();
			exchange.sendResponseHeaders(status, -1);
			exchange.close();
		})) {
			var registry = new SimpleMeterRegistry();
			var client = client(server, registry, properties(server, 3, 2, 100, 1));

			assertThatThrownBy(() -> client.analyze(ticket(), "trace-no-retry-" + status))
				.isNotInstanceOf(AiServiceCallException.class);
			assertThat(requests).hasValue(1);
			assertThat(counter(registry, "support.copilot.ai.boundary.fallbacks", "reason", "ai_service_error"))
				.isZero();
		}
	}

	@Test
	void timeoutCancelsTheAttemptWithoutRetrying() throws Exception {
		var entered = new CountDownLatch(1);
		var release = new CountDownLatch(1);
		var requests = new AtomicInteger();
		try (var server = server(exchange -> {
			requests.incrementAndGet();
			entered.countDown();
			try {
				release.await();
			} catch (InterruptedException exception) {
				Thread.currentThread().interrupt();
			} finally {
				exchange.close();
			}
		})) {
			var registry = new SimpleMeterRegistry();
			var client = client(server, registry, properties(server, 3, 2, 100, 1));

			try {
				assertThatThrownBy(() -> client.analyze(ticket(), "trace-timeout"))
					.isInstanceOfSatisfying(AiServiceCallException.class, exception ->
						assertThat(exception.getFallbackReason()).isEqualTo(FallbackReason.AI_SERVICE_TIMEOUT)
					);
				assertThat(entered.await(1, TimeUnit.SECONDS)).isTrue();
				assertThat(requests).hasValue(1);
				assertThat(counter(registry, "support.copilot.ai.boundary.timeouts", "stage", "java_deadline"))
					.isEqualTo(1);
			} finally {
				release.countDown();
			}
		}
	}

	@Test
	void pythonProcessingDeadlineIsTerminalAndNeverRetried() throws Exception {
		var requests = new AtomicInteger();
		try (var server = server(exchange -> {
			requests.incrementAndGet();
			exchange.sendResponseHeaders(504, -1);
			exchange.close();
		})) {
			var registry = new SimpleMeterRegistry();
			var client = client(server, registry, properties(server, 3, 10, 1_000, 1));

			assertThatThrownBy(() -> client.analyze(ticket(), "trace-python-deadline"))
				.isInstanceOfSatisfying(AiServiceCallException.class, exception ->
					assertThat(exception.getFallbackReason()).isEqualTo(FallbackReason.PROCESSING_TIMEOUT)
				);

			assertThat(requests).hasValue(1);
			assertThat(counter(registry, "support.copilot.ai.boundary.timeouts", "stage", "python_deadline"))
				.isEqualTo(1);
		}
	}

	@Test
	void malformedSuccessPayloadSurfacesAsContractErrorWithoutFallback() throws Exception {
		var requests = new AtomicInteger();
		try (var server = server(exchange -> {
			requests.incrementAndGet();
			respond(exchange, 200, "{not-json");
		})) {
			var registry = new SimpleMeterRegistry();
			var client = client(server, registry, properties(server, 3, 2, 100, 1));

			assertThatThrownBy(() -> client.analyze(ticket(), "trace-malformed"))
				.isInstanceOf(AiServiceContractException.class)
				.isNotInstanceOf(AiServiceCallException.class);
			assertThat(requests).hasValue(1);
			assertThat(registry.find("support.copilot.ai.boundary.fallbacks").counters()).isEmpty();
		}
	}

	@Test
	void circuitOpensAndSubsequentCallFailsWithoutReachingTheWire() throws Exception {
		var requests = new AtomicInteger();
		try (var server = server(exchange -> {
			requests.incrementAndGet();
			exchange.sendResponseHeaders(503, -1);
			exchange.close();
		})) {
			var registry = new SimpleMeterRegistry();
			var client = client(server, registry, properties(server, 1, 2, 100, 1));

			for (var attempt = 0; attempt < 2; attempt++) {
				assertThatThrownBy(() -> client.analyze(ticket(), "trace-circuit-prime"))
					.isInstanceOf(AiServiceCallException.class);
			}
			assertThatThrownBy(() -> client.analyze(ticket(), "trace-circuit-open"))
				.isInstanceOf(AiServiceCallException.class);

			assertThat(requests).hasValue(2);
			assertThat(counter(registry, "support.copilot.ai.boundary.circuit.rejected", "state", "open"))
				.isEqualTo(1);
		}
	}

	@Test
	void bulkheadRejectsConcurrentCallWithoutReachingTheWire() throws Exception {
		var entered = new CountDownLatch(1);
		var release = new CountDownLatch(1);
		var requests = new AtomicInteger();
		try (var server = server(exchange -> {
			requests.incrementAndGet();
			entered.countDown();
			try {
				release.await();
				respond(exchange, 200, successBody("trace-bulkhead-first", "mock"));
			} catch (InterruptedException exception) {
				Thread.currentThread().interrupt();
				exchange.close();
			}
		})) {
			var registry = new SimpleMeterRegistry();
			var client = client(server, registry, properties(server, 1, 10, 1_000, 1));
			try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
				var first = executor.submit(() -> client.analyze(ticket(), "trace-bulkhead-first"));
				assertThat(entered.await(1, TimeUnit.SECONDS)).isTrue();

				assertThatThrownBy(() -> client.analyze(ticket(), "trace-bulkhead-rejected"))
					.isInstanceOf(AiServiceCallException.class);
				assertThat(requests).hasValue(1);
				assertThat(counter(registry, "support.copilot.ai.boundary.bulkhead.rejected", "bulkhead", "ai"))
					.isEqualTo(1);

				release.countDown();
				assertThat(first.get(1, TimeUnit.SECONDS).mode()).isEqualTo("mock");
			}
		}
	}

	@Test
	void tracePropagatesAndLogsExcludePayloadAndCredentials() throws Exception {
		var requests = new AtomicInteger();
		var traceHeader = new AtomicReference<String>();
		var authHeader = new AtomicReference<String>();
		var logger = (ch.qos.logback.classic.Logger) org.slf4j.LoggerFactory.getLogger(AiServiceClient.class);
		var appender = new ListAppender<ILoggingEvent>();
		appender.start();
		logger.addAppender(appender);
		try (var server = server(exchange -> {
			traceHeader.set(exchange.getRequestHeaders().getFirst("X-Trace-Id"));
			authHeader.set(exchange.getRequestHeaders().getFirst("X-Internal-Service-Token"));
			if (requests.incrementAndGet() == 1) {
				exchange.sendResponseHeaders(503, -1);
				exchange.close();
				return;
			}
			respond(exchange, 200, successBody("trace-redaction", "mock"));
		})) {
			var registry = new SimpleMeterRegistry();
			var client = client(server, registry, properties(server, 3, 2, 100, 1));

			client.analyze(ticket(), "trace-redaction");

			assertThat(traceHeader).hasValue("trace-redaction");
			assertThat(authHeader).hasValue(INTERNAL_TOKEN);
			assertThat(appender.list)
				.extracting(ILoggingEvent::getFormattedMessage)
				.allSatisfy(message -> assertThat(message)
					.doesNotContain(SENSITIVE_CONTENT, INTERNAL_TOKEN));
			assertThat(appender.list)
				.extracting(ILoggingEvent::getFormattedMessage)
				.anyMatch(message -> message.startsWith("ai.boundary.retry"));
			assertThat(appender.list)
				.flatExtracting(ILoggingEvent::getKeyValuePairs)
				.anySatisfy(pair -> {
					assertThat(pair.key).isEqualTo("trace_id");
					assertThat(pair.value).isEqualTo("trace-redaction");
				});
		} finally {
			logger.detachAppender(appender);
			appender.stop();
		}
	}

	private AiServiceClient client(
		TestServer server,
		SimpleMeterRegistry registry,
		AiServiceProperties properties
	) {
		return new AiServiceClient(properties, INTERNAL_TOKEN, registry);
	}

	private AiServiceProperties properties(
		TestServer server,
		int maxAttempts,
		int minimumCircuitCalls,
		long timeoutMs,
		int maxConcurrentCalls
	) {
		return new AiServiceProperties(
			server.baseUrl(),
			timeoutMs,
			maxAttempts,
			0,
			Math.max(2, minimumCircuitCalls),
			minimumCircuitCalls,
			50,
			30_000,
			maxConcurrentCalls,
			0
		);
	}

	private double counter(
		SimpleMeterRegistry registry,
		String name,
		String tagName,
		String tagValue
	) {
		var counter = registry.find(name).tag(tagName, tagValue).counter();
		return counter == null ? 0 : counter.count();
	}

	private Ticket ticket() {
		var ticket = new Ticket();
		ticket.setId("ticket-resilience");
		ticket.setTicketNo("SC-RESILIENCE");
		ticket.setSubject("Enterprise login failure");
		ticket.setDescription(SENSITIVE_CONTENT);
		ticket.setLanguage("en-US");
		ticket.setCustomerTier("ENTERPRISE");
		ticket.setCategory("ACCOUNT_ACCESS");
		ticket.setPriority("HIGH");
		ticket.setCreatedAt(Instant.now());
		return ticket;
	}

	private String successBody(String traceId, String mode) {
		return """
			{"id":"analysis-resilience","traceId":"%s","status":"SUCCEEDED",\
			"mode":"%s","modelName":"contract-provider","promptVersion":"ticket-analysis-v1"}
			""".formatted(traceId, mode);
	}

	private void respond(com.sun.net.httpserver.HttpExchange exchange, int status, String content)
		throws java.io.IOException {
		var body = content.getBytes(StandardCharsets.UTF_8);
		exchange.getResponseHeaders().add("Content-Type", "application/json");
		exchange.sendResponseHeaders(status, body.length);
		exchange.getResponseBody().write(body);
		exchange.close();
	}

	private TestServer server(com.sun.net.httpserver.HttpHandler handler) throws Exception {
		return new TestServer(handler);
	}

	private static final class TestServer implements AutoCloseable {
		private final HttpServer server;
		private final java.util.concurrent.ExecutorService executor;

		private TestServer(com.sun.net.httpserver.HttpHandler handler) throws Exception {
			server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
			executor = Executors.newVirtualThreadPerTaskExecutor();
			server.createContext("/analyze", handler);
			server.setExecutor(executor);
			server.start();
		}

		private String baseUrl() {
			return "http://127.0.0.1:" + server.getAddress().getPort();
		}

		@Override
		public void close() {
			server.stop(0);
			executor.shutdownNow();
		}
	}
}
