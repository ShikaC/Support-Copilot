package com.cyagent.supportcopilot.analysis;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.net.InetSocketAddress;
import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.Executors;

import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.ResourceAccessException;

import com.cyagent.supportcopilot.ticket.Ticket;

class AiServiceClientTests {

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
					.isInstanceOf(ResourceAccessException.class);
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
