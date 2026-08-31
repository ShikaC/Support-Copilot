package com.cyagent.supportcopilot.idempotency;

import static com.cyagent.supportcopilot.common.MySqlTestSupport.container;
import static com.cyagent.supportcopilot.common.MySqlTestSupport.createDatabase;
import static com.cyagent.supportcopilot.idempotency.CommandIdempotencyAssertions.assertCounts;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.context.ConfigurableApplicationContext;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.mysql.MySQLContainer;

import tools.jackson.databind.ObjectMapper;

import com.cyagent.supportcopilot.analysis.AnalysisCommandService;
import com.cyagent.supportcopilot.common.TestTrustedActors;
import com.cyagent.supportcopilot.ticket.TicketRepository;

@EnabledIfEnvironmentVariable(named = "SUPPORT_COPILOT_RUN_MYSQL_TESTS", matches = "true")
@Testcontainers(disabledWithoutDocker = true)
class CommandIdempotencyMySqlIntegrationTests {

	@Container
	static final MySQLContainer MYSQL = container("support_copilot_idempotency");

	@Test
	void concurrentSameKeyReusesOneResultAndRestartRejectsAConflictingFingerprint() throws Exception {
		try (var rig = new CommandIdempotencyTestRig(createDatabase(
			MYSQL, "support_copilot_idempotency_concurrent"
		));
			var firstContext = rig.startContext();
			var secondContext = rig.startContext()) {
			var ticket = rig.ticket("ticket-mysql-concurrent");
			firstContext.getBean(TicketRepository.class).saveAndFlush(ticket);
			var response = firstContext.getBean(com.cyagent.supportcopilot.analysis.MockAnalysisFactory.class)
				.createMock(ticket);
			rig.aiServer().respondWith(firstContext.getBean(ObjectMapper.class).writeValueAsString(response));
			rig.aiServer().block();
			com.cyagent.supportcopilot.analysis.AnalysisResponse original;

			try (var executor = Executors.newFixedThreadPool(2)) {
				var ready = new CountDownLatch(2);
				var start = new CountDownLatch(1);
				var gate = new StartGate(ready, start);
				var first = executor.submit(() -> concurrentAnalyze(
					firstContext, ticket.getId(), gate
				));
				var second = executor.submit(() -> concurrentAnalyze(
					secondContext, ticket.getId(), gate
				));
				assertThat(ready.await(5, TimeUnit.SECONDS)).isTrue();
				start.countDown();
				assertThat(rig.aiServer().awaitInvocation()).isTrue();
				assertThat(rig.awaitLeaseRenewal(firstContext, "mysql-shared-key-0001")).isTrue();
				rig.aiServer().release();
				original = first.get(10, TimeUnit.SECONDS);
				assertThat(second.get(10, TimeUnit.SECONDS)).isEqualTo(original);
				assertThat(rig.aiServer().invocations()).isEqualTo(1);
			}

			assertCounts(firstContext, 1, 0, 1, 1);
			secondContext.close();
			try (var restarted = rig.startContext()) {
				assertThat(analyze(restarted, ticket.getId(), "mysql-shared-key-0001")).isEqualTo(original);
				assertThatThrownBy(() -> analyze(
					restarted, "ticket-conflicting-fingerprint", "mysql-shared-key-0001"
				)).isInstanceOf(IdempotencyConflictException.class);
				assertThat(rig.aiServer().invocations()).isEqualTo(1);
				assertCounts(restarted, 1, 0, 1, 1);
			}
		}
	}

	@Test
	void expiredOwnerLeaseIsRecoveredAfterApplicationRestart() throws Exception {
		try (var rig = new CommandIdempotencyTestRig(createDatabase(
			MYSQL, "support_copilot_idempotency_recovery"
		)); var abandoned = rig.startContext()) {
			var ticket = rig.ticket("ticket-mysql-owner-recovery");
			abandoned.getBean(TicketRepository.class).saveAndFlush(ticket);
			var request = abandoned.getBean(CommandRequestFactory.class)
				.analysis(IdempotencyKey.parse("mysql-owner-recovery-0001"), ticket.getId());
			assertThat(abandoned.getBean(CommandIdempotencyStore.class).resolve(request))
				.isInstanceOf(CommandResolution.Owned.class);
			abandoned.close();

			try (var restarted = rig.startContext()) {
				var response = restarted.getBean(com.cyagent.supportcopilot.analysis.MockAnalysisFactory.class)
					.createMock(ticket);
				rig.aiServer().respondWith(restarted.getBean(ObjectMapper.class).writeValueAsString(response));

				assertThat(analyze(restarted, ticket.getId(), "mysql-owner-recovery-0001"))
					.usingRecursiveComparison()
					.ignoringFields("traceId")
					.isEqualTo(response);
				assertThat(rig.aiServer().invocations()).isEqualTo(1);
				assertCounts(restarted, 1, 0, 1, 1);
			}
		}
	}

	private com.cyagent.supportcopilot.analysis.AnalysisResponse concurrentAnalyze(
		ConfigurableApplicationContext context,
		String ticketId,
		StartGate gate
	) throws Exception {
		gate.ready().countDown();
		if (!gate.start().await(5, TimeUnit.SECONDS)) {
			throw new IllegalStateException("Concurrent MySQL commands were not released");
		}
		return analyze(context, ticketId, "mysql-shared-key-0001");
	}

	private com.cyagent.supportcopilot.analysis.AnalysisResponse analyze(
		ConfigurableApplicationContext context,
		String ticketId,
		String key
	) {
		TestTrustedActors.authenticate("mysql-idempotency-agent", "SUPPORT_AGENT");
		try {
			return context.getBean(AnalysisCommandService.class).analyze(ticketId, IdempotencyKey.parse(key));
		} finally {
			TestTrustedActors.clear();
		}
	}

	private record StartGate(CountDownLatch ready, CountDownLatch start) {
	}
}
