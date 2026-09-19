package com.cyagent.supportcopilot.idempotency;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static com.cyagent.supportcopilot.idempotency.CommandIdempotencyAssertions.assertCounts;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.http.MediaType.APPLICATION_JSON;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.List;

import tools.jackson.databind.ObjectMapper;

import org.junit.jupiter.api.Test;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import com.cyagent.supportcopilot.analysis.AnalysisCommandService;
import com.cyagent.supportcopilot.analysis.AnalysisPersistenceService;
import com.cyagent.supportcopilot.analysis.AnalysisRunRepository;
import com.cyagent.supportcopilot.analysis.AnalysisService;
import com.cyagent.supportcopilot.analysis.IdempotentAnalysisPersistence;
import com.cyagent.supportcopilot.common.CanonicalAnalysisFixture;
import com.cyagent.supportcopilot.knowledge.KnowledgeCorpusStore;
import com.cyagent.supportcopilot.knowledge.KnowledgeActiveRelease;
import com.cyagent.supportcopilot.knowledge.KnowledgeActiveReleaseRepository;
import com.cyagent.supportcopilot.knowledge.KnowledgeReleaseRepository;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewCommandService;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewController;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewService;
import com.cyagent.supportcopilot.common.ApiExceptionHandler;
import com.cyagent.supportcopilot.common.TestTrustedActors;
import com.cyagent.supportcopilot.ticket.TicketController;
import com.cyagent.supportcopilot.ticket.TicketRepository;
import com.cyagent.supportcopilot.ticket.TicketService;

class CommandIdempotencyIntegrationTests {

	@Test
	void analysisRequiresAnIdempotencyKeyBeforeInvokingTheCommand() throws Exception {
		var commandService = mock(AnalysisCommandService.class);
		var mvc = MockMvcBuilders.standaloneSetup(new TicketController(
			mock(TicketService.class), mock(AnalysisService.class), commandService
		))
			.setControllerAdvice(new ApiExceptionHandler(mock(TicketRepository.class)))
			.build();

		mvc.perform(post("/api/tickets/ticket-10042/analyze"))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.code").value("IDEMPOTENCY_KEY_REQUIRED"))
			.andExpect(jsonPath("$.traceId").isNotEmpty());
		verify(commandService, never()).analyze(
			org.mockito.ArgumentMatchers.anyString(), org.mockito.ArgumentMatchers.any()
		);
	}

	@Test
	void reviewRejectsAMalformedIdempotencyKeyBeforeInvokingTheCommand() throws Exception {
		var commandService = mock(AnalysisReviewCommandService.class);
		var mvc = MockMvcBuilders.standaloneSetup(new AnalysisReviewController(
			mock(AnalysisReviewService.class), commandService
		))
			.setControllerAdvice(new ApiExceptionHandler(mock(TicketRepository.class)))
			.build();

		mvc.perform(post("/api/tickets/ticket-10042/analyses/analysis-1/reviews")
				.header("Idempotency-Key", "bad key")
				.contentType(APPLICATION_JSON)
				.content("{\"replyContent\":\"reviewed\"}"))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.code").value("INVALID_IDEMPOTENCY_KEY"))
			.andExpect(jsonPath("$.traceId").isNotEmpty());
		verify(commandService, never()).review(
			org.mockito.ArgumentMatchers.anyString(),
			org.mockito.ArgumentMatchers.anyString(),
			org.mockito.ArgumentMatchers.anyString(),
			org.mockito.ArgumentMatchers.any()
		);
	}

	@Test
	void concurrentContextsConvergeAndRestartReplaysWithoutNewEffects() throws Exception {
		try (var rig = new CommandIdempotencyTestRig();
			var firstContext = rig.startContext();
			var secondContext = rig.startContext()) {
			var ticket = rig.ticket("ticket-cross-context");
			firstContext.getBean(TicketRepository.class).saveAndFlush(ticket);
			var response = CanonicalAnalysisFixture.create(ticket, firstContext.getBean(KnowledgeCorpusStore.class));
			rig.aiServer().respondWith(firstContext.getBean(ObjectMapper.class).writeValueAsString(response));
			rig.aiServer().block();
			com.cyagent.supportcopilot.analysis.AnalysisResponse original;

			try (var executor = Executors.newFixedThreadPool(2)) {
				var commandsReady = new CountDownLatch(2);
				var startCommands = new CountDownLatch(1);
				var first = executor.submit(() -> {
					commandsReady.countDown();
					if (!startCommands.await(2, TimeUnit.SECONDS)) {
						throw new IllegalStateException("Concurrent commands were not released");
					}
					return analyze(firstContext, ticket.getId(), "analysis-shared-key-0001");
				});
				var second = executor.submit(() -> {
					commandsReady.countDown();
					if (!startCommands.await(2, TimeUnit.SECONDS)) {
						throw new IllegalStateException("Concurrent commands were not released");
					}
					return analyze(secondContext, ticket.getId(), "analysis-shared-key-0001");
				});
				assertThat(commandsReady.await(2, TimeUnit.SECONDS)).isTrue();
				startCommands.countDown();
				assertThat(rig.aiServer().awaitInvocation()).isTrue();
				assertThat(rig.awaitLeaseRenewal(firstContext, "analysis-shared-key-0001")).isTrue();
				rig.aiServer().release();
				original = first.get(3, TimeUnit.SECONDS);
				assertThat(second.get(3, TimeUnit.SECONDS)).isEqualTo(original);
				assertThat(rig.aiServer().invocations()).isEqualTo(1);
			}

			assertCounts(firstContext, 1, 0, 1, 1);
			secondContext.close();
			try (var restarted = rig.startContext()) {
				assertThat(analyze(restarted, ticket.getId(), "analysis-shared-key-0001")).isEqualTo(original);
				assertThat(rig.aiServer().invocations()).isEqualTo(1);
				assertCounts(restarted, 1, 0, 1, 1);
					assertThatThrownBy(() -> analyze(restarted, "ticket-different", "analysis-shared-key-0001"))
						.isInstanceOf(IdempotencyConflictException.class);
					assertCounts(restarted, 1, 0, 1, 1);

					archiveActiveRelease(restarted);
					assertThatThrownBy(() -> analyze(restarted, ticket.getId(), "analysis-shared-key-0001"))
						.isInstanceOf(AccessDeniedException.class);
					assertThat(rig.aiServer().invocations()).isEqualTo(1);
					assertCounts(restarted, 1, 0, 1, 1);
			}
		}
	}

	@Test
	void reviewReplayAndFingerprintConflictCreateOneReviewAndAuditEvent() throws Exception {
		try (var rig = new CommandIdempotencyTestRig();
			var first = rig.startContext();
			var second = rig.startContext()) {
			var ticket = rig.ticket("ticket-review-replay");
			first.getBean(TicketRepository.class).saveAndFlush(ticket);
			var analysis = CanonicalAnalysisFixture.create(ticket, first.getBean(KnowledgeCorpusStore.class));
			TestTrustedActors.authenticateWithScopes("analysis-agent", List.of("BILLING"), "SUPPORT_AGENT");
			first.getBean(AnalysisPersistenceService.class).persist(ticket.getId(), ticket.getVersion(), analysis);
			TestTrustedActors.clear();

			TestTrustedActors.authenticateWithScopes("reviewer-one", List.of("BILLING"), "SUPPORT_REVIEWER");
			var original = first.getBean(AnalysisReviewCommandService.class).review(
				ticket.getId(), analysis.id(), analysis.suggestedReply().content(),
				IdempotencyKey.parse("review-replay-key-0001")
			);
			TestTrustedActors.clear();
			TestTrustedActors.authenticateWithScopes("reviewer-one", List.of("BILLING"), "SUPPORT_REVIEWER");
			var replay = second.getBean(AnalysisReviewCommandService.class).review(
				ticket.getId(), analysis.id(), analysis.suggestedReply().content(),
				IdempotencyKey.parse("review-replay-key-0001")
			);
			assertThat(replay).isEqualTo(original);
			assertThatThrownBy(() -> second.getBean(AnalysisReviewCommandService.class).review(
				ticket.getId(), analysis.id(), "different reviewed content",
				IdempotencyKey.parse("review-replay-key-0001")
			)).isInstanceOf(IdempotencyConflictException.class);
			assertThatThrownBy(() -> second.getBean(AnalysisReviewCommandService.class).reject(
				ticket.getId(), analysis.id(), "different command",
				IdempotencyKey.parse("review-replay-key-0001")
			)).isInstanceOf(IdempotencyConflictException.class);
			TestTrustedActors.authenticateWithScopes("reviewer-two", List.of("BILLING"), "SUPPORT_REVIEWER");
			assertThatThrownBy(() -> second.getBean(AnalysisReviewCommandService.class).review(
				ticket.getId(), analysis.id(), analysis.suggestedReply().content(),
				IdempotencyKey.parse("review-replay-key-0001")
			)).isInstanceOf(IdempotencyConflictException.class);
			TestTrustedActors.clear();

			assertCounts(first, 1, 1, 2, 1);
			archiveActiveRelease(second);
			TestTrustedActors.authenticateWithScopes("reviewer-one", List.of("BILLING"), "SUPPORT_REVIEWER");
			try {
				assertThatThrownBy(() -> second.getBean(AnalysisReviewCommandService.class).review(
					ticket.getId(), analysis.id(), analysis.suggestedReply().content(),
					IdempotencyKey.parse("review-replay-key-0001")
				)).isInstanceOf(AccessDeniedException.class);
			} finally {
				TestTrustedActors.clear();
			}
			assertThat(rig.aiServer().invocations()).isZero();
			assertCounts(first, 1, 1, 2, 1);
		}
	}

	@Test
	void expiredOwnerIsRecoverableAndCompletionFailureRollsBackBusinessData() throws Exception {
		try (var rig = new CommandIdempotencyTestRig(); var abandoned = rig.startContext()) {
			var ticket = rig.ticket("ticket-owner-recovery");
			abandoned.getBean(TicketRepository.class).saveAndFlush(ticket);
			TestTrustedActors.authenticateWithScopes("task-6-agent", List.of("BILLING"), "SUPPORT_AGENT");
			var request = abandoned.getBean(CommandRequestFactory.class)
				.analysis(IdempotencyKey.parse("owner-recovery-key-0001"), ticket.getId());
			TestTrustedActors.clear();
			var resolution = abandoned.getBean(CommandIdempotencyStore.class).resolve(request);
			assertThat(resolution).isInstanceOf(CommandResolution.Owned.class);
			abandoned.close();

			try (var recovered = rig.startContext()) {
				var response = CanonicalAnalysisFixture.create(ticket, recovered.getBean(KnowledgeCorpusStore.class));
				rig.aiServer().respondWith(recovered.getBean(ObjectMapper.class).writeValueAsString(response));
				assertThat(analyze(recovered, ticket.getId(), "owner-recovery-key-0001"))
					.usingRecursiveComparison()
					.ignoringFields("traceId")
					.isEqualTo(response);
				assertCounts(recovered, 1, 0, 1, 1);

				var rollbackTicket = rig.ticket("ticket-completion-rollback");
				recovered.getBean(TicketRepository.class).saveAndFlush(rollbackTicket);
				var rollbackResponse = CanonicalAnalysisFixture.create(rollbackTicket, recovered.getBean(KnowledgeCorpusStore.class));
				TestTrustedActors.authenticateWithScopes("rollback-agent", List.of("BILLING"), "SUPPORT_AGENT");
				assertThatThrownBy(() -> recovered.getBean(AnalysisPersistenceService.class).persistIdempotent(
					new IdempotentAnalysisPersistence(
						rollbackTicket.getId(), rollbackTicket.getVersion(), rollbackResponse,
						new CommandOwnership("missing-key-ownership", "missing-owner-token")
					)
				)).isInstanceOf(IllegalStateException.class);
				TestTrustedActors.clear();
				assertThat(recovered.getBean(AnalysisRunRepository.class).existsById(rollbackResponse.id())).isFalse();
				assertThat(recovered.getBean(TicketRepository.class).findById(rollbackTicket.getId()).orElseThrow()
					.getVersion()).isEqualTo(rollbackTicket.getVersion());
				assertCounts(recovered, 1, 0, 1, 1);
			}
		}
	}

	@Test
	void migrationEnforcesGlobalKeyUniquenessAndCreatesOperationalIndexes() throws Exception {
		try (var rig = new CommandIdempotencyTestRig(); var context = rig.startContext()) {
			var jdbc = context.getBean(JdbcTemplate.class);
			jdbc.update("""
				insert into command_idempotency (
				  id, idempotency_key, request_fingerprint, command_type, route_scope,
				  status, owner_token, lease_expires_at, created_at, updated_at
				) values (?, ?, ?, ?, ?, ?, ?, current_timestamp, current_timestamp, current_timestamp)
				""",
				"command-unique-1", "database-unique-key-0001", "a".repeat(64),
				"ANALYZE_TICKET", "POST:/api/tickets/{ticketId}/analyze", "PENDING", "owner-1"
			);
			assertThatThrownBy(() -> jdbc.update("""
				insert into command_idempotency (
				  id, idempotency_key, request_fingerprint, command_type, route_scope,
				  status, owner_token, lease_expires_at, created_at, updated_at
				) values (?, ?, ?, ?, ?, ?, ?, current_timestamp, current_timestamp, current_timestamp)
				""",
				"command-unique-2", "database-unique-key-0001", "b".repeat(64),
				"REVIEW_ANALYSIS", "POST:/different", "PENDING", "owner-2"
			)).isInstanceOf(DataIntegrityViolationException.class);
			assertThat(jdbc.queryForList("""
				select index_name from information_schema.indexes
				where table_name = 'COMMAND_IDEMPOTENCY'
				""", String.class)).contains(
				"IDX_COMMAND_IDEMPOTENCY_PENDING_LEASE",
				"IDX_COMMAND_IDEMPOTENCY_UPDATED"
			);
			assertThat(jdbc.queryForObject("""
				select count(*) from information_schema.table_constraints where table_name = 'COMMAND_IDEMPOTENCY'
				and constraint_name = 'UK_COMMAND_IDEMPOTENCY_KEY' and constraint_type = 'UNIQUE'
				""", Long.class)).isEqualTo(1);
		}
	}

	private void archiveActiveRelease(ConfigurableApplicationContext context) {
		var pointer = context.getBean(KnowledgeActiveReleaseRepository.class)
			.findById(KnowledgeActiveRelease.SINGLETON_ID).orElseThrow();
		var releases = context.getBean(KnowledgeReleaseRepository.class);
		var release = releases.findById(pointer.getReleaseId()).orElseThrow();
		release.archive();
		releases.saveAndFlush(release);
	}

	private com.cyagent.supportcopilot.analysis.AnalysisResponse analyze(
		ConfigurableApplicationContext context,
		String ticketId,
		String key
	) {
		TestTrustedActors.authenticateWithScopes("task-6-agent", List.of("BILLING"), "SUPPORT_AGENT");
		try {
			return context.getBean(AnalysisCommandService.class).analyze(ticketId, IdempotencyKey.parse(key));
		} finally {
			TestTrustedActors.clear();
		}
	}

}
