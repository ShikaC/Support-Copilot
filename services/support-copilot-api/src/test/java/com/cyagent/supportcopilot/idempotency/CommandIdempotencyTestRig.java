package com.cyagent.supportcopilot.idempotency;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import com.sun.net.httpserver.HttpServer;

import org.flywaydb.core.Flyway;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.jdbc.core.JdbcTemplate;

import com.cyagent.supportcopilot.SupportCopilotApiApplication;
import com.cyagent.supportcopilot.ticket.Ticket;

final class CommandIdempotencyTestRig implements AutoCloseable {

	private final Path directory;
	private final Path databasePath;
	private final CountingAiServer aiServer;

	CommandIdempotencyTestRig() throws IOException {
		directory = Files.createTempDirectory("support-copilot-task-6-");
		databasePath = directory.resolve("shared-command-db");
		aiServer = new CountingAiServer();
	}

	ConfigurableApplicationContext startContext() {
		Flyway.configure()
			.dataSource(databaseUrl(), "sa", "")
			.locations("classpath:db/migration")
			.load()
			.migrate();
		return new SpringApplicationBuilder(SupportCopilotApiApplication.class)
			.web(WebApplicationType.SERVLET)
			.run(
				"--spring.profiles.active=test",
				"--server.port=0",
				"--spring.datasource.url=" + databaseUrl(),
				"--spring.jpa.hibernate.ddl-auto=validate",
				"--spring.flyway.enabled=true",
				"--spring.flyway.locations=classpath:db/migration",
				"--support-copilot.demo-fixtures.enabled=false",
				"--support-copilot.idempotency.lease-duration=PT0.3S",
				"--support-copilot.idempotency.wait-timeout=PT3S",
				"--support-copilot.idempotency.poll-interval=PT0.02S",
				"--ai.service.base-url=" + aiServer.baseUrl(),
				"--ai.service.timeout-ms=5000"
			);
	}

	CountingAiServer aiServer() {
		return aiServer;
	}

	Ticket ticket(String id) {
		var now = Instant.now();
		var ticket = new Ticket();
		ticket.setId(id);
		ticket.setTicketNo("SC-" + id.substring(Math.max(0, id.length() - 12)).toUpperCase());
		ticket.setChannel("EMAIL");
		ticket.setCustomerName("Synthetic Customer");
		ticket.setCustomerCompany("Task 6 Verification");
		ticket.setCustomerTier("STANDARD");
		ticket.setSubject("Durable command test");
		ticket.setDescription("Synthetic test content that must never enter the fingerprint column.");
		ticket.setLanguage("en-US");
		ticket.setCategory("BILLING");
		ticket.setPriority("HIGH");
		ticket.setStatus("NEW");
		ticket.setSlaDeadline(now.plus(Duration.ofHours(8)));
		ticket.setCreatedAt(now);
		ticket.setUpdatedAt(now);
		return ticket;
	}

	boolean awaitLeaseRenewal(ConfigurableApplicationContext context, String idempotencyKey)
		throws InterruptedException {
		var jdbc = context.getBean(JdbcTemplate.class);
		var initial = jdbc.queryForMap(
			"select owner_token, updated_at from command_idempotency where idempotency_key = ?",
			idempotencyKey
		);
		var ownerToken = initial.get("OWNER_TOKEN");
		var updatedAt = initial.get("UPDATED_AT");
		var deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(2);
		while (System.nanoTime() < deadline) {
			var current = jdbc.queryForMap(
				"select owner_token, updated_at from command_idempotency where idempotency_key = ?",
				idempotencyKey
			);
			if (ownerToken.equals(current.get("OWNER_TOKEN")) && !updatedAt.equals(current.get("UPDATED_AT"))) {
				return true;
			}
			Thread.sleep(10);
		}
		return false;
	}

	@Override
	public void close() throws Exception {
		aiServer.close();
		try (var files = Files.list(directory)) {
			files.forEach(this::delete);
		}
		Files.deleteIfExists(directory);
	}

	private String databaseUrl() {
		return "jdbc:h2:file:" + databasePath
			+ ";MODE=MySQL;DB_CLOSE_ON_EXIT=FALSE;LOCK_TIMEOUT=10000";
	}

	private void delete(Path path) {
		try {
			Files.deleteIfExists(path);
		} catch (IOException exception) {
			throw new IllegalStateException("Unable to clean Task 6 H2 file", exception);
		}
	}

	static final class CountingAiServer implements AutoCloseable {

		private final HttpServer server;
		private final AtomicInteger invocations = new AtomicInteger();
		private volatile String responseJson = "{}";
		private volatile CountDownLatch started = new CountDownLatch(0);
		private volatile CountDownLatch release = new CountDownLatch(0);

		CountingAiServer() throws IOException {
			server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
			server.createContext("/analyze", exchange -> {
				invocations.incrementAndGet();
				started.countDown();
				try {
					release.await(5, TimeUnit.SECONDS);
				} catch (InterruptedException exception) {
					Thread.currentThread().interrupt();
				}
				var body = responseJson.getBytes(StandardCharsets.UTF_8);
				exchange.getResponseHeaders().set("Content-Type", "application/json");
				exchange.sendResponseHeaders(200, body.length);
				exchange.getResponseBody().write(body);
				exchange.close();
			});
			server.start();
		}

		String baseUrl() {
			return "http://127.0.0.1:" + server.getAddress().getPort();
		}

		void respondWith(String json) {
			responseJson = json;
		}

		void block() {
			started = new CountDownLatch(1);
			release = new CountDownLatch(1);
		}

		boolean awaitInvocation() throws InterruptedException {
			return started.await(2, TimeUnit.SECONDS);
		}

		void release() {
			release.countDown();
		}

		int invocations() {
			return invocations.get();
		}

		@Override
		public void close() {
			release();
			server.stop(0);
		}
	}
}
