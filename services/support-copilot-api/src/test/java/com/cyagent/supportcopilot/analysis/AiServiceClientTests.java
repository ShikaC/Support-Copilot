package com.cyagent.supportcopilot.analysis;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.Executors;

import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import com.cyagent.supportcopilot.ticket.Ticket;

class AiServiceClientTests {

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
				1_000
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
				100
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
