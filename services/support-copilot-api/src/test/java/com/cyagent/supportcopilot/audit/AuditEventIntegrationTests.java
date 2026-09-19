package com.cyagent.supportcopilot.audit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.http.MediaType.APPLICATION_JSON;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.List;
import java.util.ArrayList;

import tools.jackson.databind.ObjectMapper;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.slf4j.MDC;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import com.cyagent.supportcopilot.analysis.AnalysisPersistenceService;
import com.cyagent.supportcopilot.analysis.FallbackReason;
import com.cyagent.supportcopilot.analysis.MockAnalysisFactory;
import com.cyagent.supportcopilot.analysis.TicketVersionConflictException;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewService;
import com.cyagent.supportcopilot.ticket.TicketRepository;
import com.cyagent.supportcopilot.ticket.TicketService;
import com.cyagent.supportcopilot.ticket.TicketDtos.CreateTicketRequest;
import com.cyagent.supportcopilot.ticket.TicketDomain.Channel;
import com.cyagent.supportcopilot.ticket.TicketDomain.CustomerTier;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AuditEventIntegrationTests {

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JdbcTemplate jdbcTemplate;

	@Autowired
	private ObjectMapper objectMapper;

	@Autowired
	private TicketRepository ticketRepository;

	@Autowired
	private AnalysisPersistenceService analysisPersistenceService;

	@Autowired
	private AnalysisReviewService analysisReviewService;

	@Autowired
	private MockAnalysisFactory mockAnalysisFactory;

	@Autowired
	private TicketService ticketService;

	@Autowired
	private AuditEventRecorder auditEventRecorder;

	@Autowired
	private PlatformTransactionManager transactionManager;

	@AfterEach
	void cleanUp() {
		SecurityContextHolder.clearContext();
		MDC.remove("traceId");
		jdbcTemplate.update("delete from audit_events");
		jdbcTemplate.update("delete from analysis_reviews");
		jdbcTemplate.update("delete from analysis_runs");
		jdbcTemplate.update("delete from tickets");
	}

	@Test
	void auditInsertConstraintFailureRollsBackTheBusinessWrite() {
		var ticketCountBefore = ticketRepository.count();
		var auditCountBefore = auditCount();
		authenticate("actor-" + "x".repeat(140), "SUPPORT_AGENT");
		MDC.put("traceId", "trace-audit-insert-failure");

		assertThatThrownBy(() -> ticketService.create(new CreateTicketRequest(
			Channel.EMAIL,
			"Atomicity Customer",
			"Atomicity Company",
			CustomerTier.STANDARD,
			"Atomicity subject",
			"Atomicity description",
			"zh-CN"
		))).isInstanceOf(RuntimeException.class);

		assertThat(ticketRepository.count()).isEqualTo(ticketCountBefore);
		assertThat(auditCount()).isEqualTo(auditCountBefore);
	}

	@Test
	void outerBusinessRollbackRemovesAnEventInsertedEarlierInTheTransaction() {
		authenticate("transaction-reviewer", "SUPPORT_REVIEWER");
		MDC.put("traceId", "trace-event-then-business-rollback");
		var transaction = new TransactionTemplate(transactionManager);

		assertThatThrownBy(() -> transaction.executeWithoutResult(status -> {
			auditEventRecorder.record(new AuditEventCommand(
				AuditAction.TICKET_CREATED,
				AuditTargetType.TICKET,
				"ticket-rolled-back-after-audit",
				0L,
				new AuditMetadata.None()
			));
			throw new IllegalStateException("synthetic business rollback after audit insert");
		})).isInstanceOf(IllegalStateException.class);

		assertThat(jdbcTemplate.queryForObject(
			"select count(*) from audit_events where target_id = ?",
			Long.class,
			"ticket-rolled-back-after-audit"
		)).isZero();
	}

	@Test
	void fallbackAnalysisPersistenceCreatesOneRedactedEventAndConflictCreatesNone() throws Exception {
		var ticketId = createTicket("analysis-creator", "trace-analysis-create");
		var ticket = ticketRepository.findById(ticketId).orElseThrow();
		var sourceVersion = ticket.getVersion();
		var analysis = mockAnalysisFactory.createFallback(
			ticket,
			"trace-analysis-fallback",
			FallbackReason.AI_SERVICE_UNAVAILABLE
		);
		authenticate("trusted-analysis-agent", "SUPPORT_AGENT");
		MDC.put("traceId", analysis.traceId());

		analysisPersistenceService.persist(ticketId, sourceVersion, analysis);

		var rows = jdbcTemplate.queryForList(
			"select * from audit_events where action = 'ANALYSIS_PERSISTED' and target_id = ?",
			analysis.id()
		);
		assertThat(rows).singleElement().satisfies(row -> {
			assertThat(row.get("ACTOR_SUBJECT")).isEqualTo("trusted-analysis-agent");
			assertThat(row.get("TARGET_TYPE")).isEqualTo("ANALYSIS");
			assertThat(row.get("TARGET_VERSION")).isEqualTo(sourceVersion);
			assertThat(row.get("TRACE_ID")).isEqualTo(analysis.traceId());
			assertThat(row.get("METADATA_JSON").toString()).isEqualTo(
				"{\"mode\":\"FALLBACK\",\"status\":\"FALLBACK\","
					+ "\"fallbackCategory\":\"ai_service_unavailable\",\"sourceVersion\":0,"
					+ "\"resultId\":\"" + analysis.id() + "\"}"
			);
			assertThat(row.toString()).doesNotContain(
				analysis.suggestedReply().content(),
				analysis.retrieval().hits().toString(),
				"configured-chat-model"
			);
		});
		var countAfterSuccess = auditCount();

		assertThat(org.assertj.core.api.Assertions.catchThrowable(() ->
			analysisPersistenceService.persist(ticketId, sourceVersion, analysis)
		)).isInstanceOf(TicketVersionConflictException.class);
		assertThat(auditCount()).isEqualTo(countAfterSuccess);
	}

	@Test
	void eachNewReviewDecisionCreatesOneEventWhileSameContentReplayCreatesNone() throws Exception {
		var ticketId = createTicket("review-creator", "trace-review-create");
		var ticket = ticketRepository.findById(ticketId).orElseThrow();
		var analysis = mockAnalysisFactory.createFallback(ticket, "trace-review-audit-fixture",
			com.cyagent.supportcopilot.analysis.FallbackReason.AI_SERVICE_UNAVAILABLE);
		authenticate("analysis-agent", "SUPPORT_AGENT");
		MDC.put("traceId", analysis.traceId());
		analysisPersistenceService.persist(ticketId, ticket.getVersion(), analysis);
		authenticate("trusted-reviewer", "SUPPORT_REVIEWER");

		MDC.put("traceId", "trace-review-approved");
		var approved = analysisReviewService.review(
			ticketId,
			analysis.id(),
			analysis.suggestedReply().content()
		);
		var countAfterApproval = auditCount();
		analysisReviewService.review(ticketId, analysis.id(), analysis.suggestedReply().content());
		assertThat(auditCount()).isEqualTo(countAfterApproval);

		var editedCanary = "REVIEWED_REPLY_CANARY must remain business data";
		MDC.put("traceId", "trace-review-edited");
		var edited = analysisReviewService.review(ticketId, analysis.id(), editedCanary);

		var rejectionCanary = "REJECTION_REASON_CANARY must never be audited";
		MDC.put("traceId", "trace-review-rejected");
		var rejected = analysisReviewService.reject(ticketId, analysis.id(), rejectionCanary);
		var countAfterRejection = auditCount();
		analysisReviewService.reject(ticketId, analysis.id(), rejectionCanary);
		assertThat(auditCount()).isEqualTo(countAfterRejection);

		var reviewEvents = jdbcTemplate.queryForList(
			"select * from audit_events where target_type = 'ANALYSIS_REVIEW' order by action"
		);
		assertThat(reviewEvents).hasSize(3);
		assertThat(reviewEvents).extracting(row -> row.get("ACTION")).containsExactly(
			"ANALYSIS_REVIEW_APPROVED",
			"ANALYSIS_REVIEW_EDITED",
			"ANALYSIS_REVIEW_REJECTED"
		);
		assertThat(reviewEvents).extracting(row -> row.get("TARGET_ID")).containsExactlyInAnyOrder(
			approved.id(), edited.id(), rejected.id()
		);
		assertThat(reviewEvents.toString())
			.doesNotContain(
				analysis.suggestedReply().content(),
				editedCanary,
				rejectionCanary,
				"Authorization",
				"synthetic-reviewer-jwt"
			);
	}

	@Test
	void authenticatedTicketCreatePersistsOneTrustedAuditRow() throws Exception {
		var response = mockMvc.perform(post("/api/tickets")
				.with(agentJwt("trusted-agent-subject"))
				.header("X-Trace-Id", "trace-audit-create")
				.header("X-Audit-Actor", "spoofed-browser-actor")
				.header("X-Audit-Action", "spoofed-browser-action")
				.contentType(APPLICATION_JSON)
				.content("""
					{
					  "channel": "EMAIL",
					  "customerName": "Audit Test Customer",
					  "customerCompany": "Audit Test Company",
					  "customerTier": "STANDARD",
					  "subject": "SENSITIVE_SUBJECT_CANARY",
					  "description": "SENSITIVE_DESCRIPTION_CANARY"
					}
					"""))
			.andExpect(status().isCreated())
			.andReturn();

		var ticketId = objectMapper.readTree(response.getResponse().getContentAsString())
			.get("id").asString();
		var rows = jdbcTemplate.queryForList(
			"select * from audit_events where target_id = ?",
			ticketId
		);

		assertThat(rows).singleElement().satisfies(row -> {
			assertThat(row.get("ACTOR_SUBJECT")).isEqualTo("trusted-agent-subject");
			assertThat(row.get("ACTION")).isEqualTo("TICKET_CREATED");
			assertThat(row.get("TRACE_ID")).isEqualTo("trace-audit-create");
			assertThat(row.toString())
				.doesNotContain("SENSITIVE_SUBJECT_CANARY", "SENSITIVE_DESCRIPTION_CANARY");
		});
	}

	@Test
	void auditQueryRequiresReviewerAndReturnsStableRedactedKeysetPages() throws Exception {
		var ticketIds = List.of(
			createTicket("query-agent-1", "trace-query-1"),
			createTicket("query-agent-2", "trace-query-2"),
			createTicket("query-agent-3", "trace-query-3"),
			createTicket("query-agent-4", "trace-query-4"),
			createTicket("query-agent-5", "trace-query-5")
		);
		var expectedIds = jdbcTemplate.queryForList(
			"select id from audit_events order by created_at desc, id desc",
			String.class
		);

		mockMvc.perform(get("/api/audit-events").header("X-Trace-Id", "trace-audit-anonymous"))
			.andExpect(status().isUnauthorized())
			.andExpect(jsonPath("$.traceId").value("trace-audit-anonymous"));
		mockMvc.perform(get("/api/audit-events").with(agentJwt("query-agent")))
			.andExpect(status().isForbidden());

		var observedIds = new ArrayList<String>();
		String cursor = null;
		do {
			var path = cursor == null
				? "/api/audit-events?limit=2"
				: "/api/audit-events?limit=2&cursor=" + cursor;
			var response = mockMvc.perform(get(path).with(reviewerJwt("trusted-query-reviewer")))
				.andExpect(status().isOk())
				.andReturn().getResponse().getContentAsString();
			assertThat(response).doesNotContain(
				"SENSITIVE_SUBJECT_CANARY",
				"SENSITIVE_DESCRIPTION_CANARY",
				"spoofed-browser-actor",
				"Authorization"
			);
			var page = objectMapper.readTree(response);
			page.get("items").forEach(item -> observedIds.add(item.get("id").asString()));
			cursor = page.get("nextCursor").isNull() ? null : page.get("nextCursor").asString();
		} while (cursor != null);

		assertThat(observedIds).containsExactlyElementsOf(expectedIds);
		assertThat(observedIds).doesNotHaveDuplicates();
		assertThat(observedIds).hasSize(5);

		mockMvc.perform(get("/api/audit-events")
				.with(adminJwt("trusted-query-admin"))
				.param("targetType", "TICKET")
				.param("targetId", ticketIds.get(2))
				.param("limit", "10"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items.length()").value(1))
			.andExpect(jsonPath("$.items[0].targetId").value(ticketIds.get(2)))
			.andExpect(jsonPath("$.items[0].metadata").isMap());
	}

	@Test
	void malformedAuditCursorFilterAndLimitReturnStableBadRequest() throws Exception {
		for (var path : List.of(
			"/api/audit-events?cursor=%%%",
			"/api/audit-events?targetType=NOT_A_TARGET",
			"/api/audit-events?limit=0",
			"/api/audit-events?limit=101",
			"/api/audit-events?limit=not-a-number"
		)) {
			mockMvc.perform(get(path)
					.with(reviewerJwt("trusted-query-reviewer"))
					.header("X-Trace-Id", "trace-malformed-audit"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_AUDIT_QUERY"))
				.andExpect(jsonPath("$.traceId").value("trace-malformed-audit"));
		}
		mockMvc.perform(get("/api/audit-events")
				.with(reviewerJwt("trusted-query-reviewer"))
				.header("X-Trace-Id", "trace-malformed-audit")
				.param("targetId", "   "))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.code").value("INVALID_AUDIT_QUERY"));
	}

	@Test
	void actualTicketUpdateCreatesOneEventWhileNoOpAndStaleWritesCreateNone() throws Exception {
		var ticketId = createTicket("trusted-update-agent", "trace-update-create");

		mockMvc.perform(patch("/api/tickets/{id}", ticketId)
				.with(jwt()
					.jwt(token -> token.subject("trusted-update-agent")
						.claim("roles", List.of("SUPPORT_REVIEWER", "SUPPORT_AGENT", "SUPPORT_AGENT")))
					.authorities(
						new SimpleGrantedAuthority("ROLE_SUPPORT_REVIEWER"),
						new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT"),
						new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT")
					))
				.header("X-Trace-Id", "trace-ticket-update")
				.contentType(APPLICATION_JSON)
				.content("{\"priority\":\"HIGH\",\"expectedVersion\":0}"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.version").value(1));

		var updateRows = jdbcTemplate.queryForList(
			"select * from audit_events where target_id = ? and action = 'TICKET_UPDATED'",
			ticketId
		);
		assertThat(updateRows).singleElement().satisfies(row -> {
			assertThat(row.get("TARGET_VERSION")).isEqualTo(1L);
			assertThat(row.get("TRACE_ID")).isEqualTo("trace-ticket-update");
			assertThat(row.get("ACTOR_ROLES_JSON"))
				.isEqualTo("[\"SUPPORT_AGENT\",\"SUPPORT_REVIEWER\"]");
			assertThat(row.get("METADATA_JSON").toString()).isEqualTo("{\"changedFields\":[\"PRIORITY\"]}");
		});
		var countAfterUpdate = auditCount();

		mockMvc.perform(patch("/api/tickets/{id}", ticketId)
				.with(agentJwt("trusted-update-agent"))
				.header("X-Trace-Id", "trace-ticket-noop")
				.contentType(APPLICATION_JSON)
				.content("{\"priority\":\"HIGH\",\"expectedVersion\":1}"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.version").value(1));
		assertThat(auditCount()).isEqualTo(countAfterUpdate);

		mockMvc.perform(patch("/api/tickets/{id}", ticketId)
				.with(agentJwt("trusted-update-agent"))
				.header("X-Trace-Id", "trace-ticket-stale")
				.contentType(APPLICATION_JSON)
				.content("{\"category\":\"BILLING\",\"expectedVersion\":0}"))
			.andExpect(status().isConflict());
		assertThat(auditCount()).isEqualTo(countAfterUpdate);
	}

	@Test
	void actualUnassignCreatesOneEventWhileReplayCreatesNone() throws Exception {
		var ticketId = createTicket("trusted-unassign-agent", "trace-unassign-create");
		mockMvc.perform(patch("/api/tickets/{id}", ticketId)
				.with(agentJwt("trusted-unassign-agent"))
				.contentType(APPLICATION_JSON)
				.content("{\"assigneeName\":\"Synthetic Agent\",\"expectedVersion\":0}"))
			.andExpect(status().isOk());

		mockMvc.perform(post("/api/tickets/{id}/unassign", ticketId)
				.with(agentJwt("trusted-unassign-agent"))
				.header("X-Trace-Id", "trace-ticket-unassign")
				.contentType(APPLICATION_JSON)
				.content("{\"expectedVersion\":1}"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.version").value(2));

		assertThat(jdbcTemplate.queryForList(
			"select * from audit_events where target_id = ? and action = 'TICKET_UNASSIGNED'",
			ticketId
		)).singleElement().satisfies(row -> {
			assertThat(row.get("TARGET_VERSION")).isEqualTo(2L);
			assertThat(row.get("METADATA_JSON").toString())
				.isEqualTo("{\"changedFields\":[\"ASSIGNEE\"]}");
		});
		var countAfterUnassign = auditCount();

		mockMvc.perform(post("/api/tickets/{id}/unassign", ticketId)
				.with(agentJwt("trusted-unassign-agent"))
				.contentType(APPLICATION_JSON)
				.content("{\"expectedVersion\":2}"))
			.andExpect(status().isOk());
		assertThat(auditCount()).isEqualTo(countAfterUnassign);
	}

	private org.springframework.test.web.servlet.request.RequestPostProcessor agentJwt(String subject) {
		return jwt()
			.jwt(token -> token.subject(subject).claim("roles", List.of("SUPPORT_AGENT")))
			.authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT"));
	}

	private org.springframework.test.web.servlet.request.RequestPostProcessor reviewerJwt(String subject) {
		return jwt()
			.jwt(token -> token.subject(subject).claim("roles", List.of("SUPPORT_REVIEWER")))
			.authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_REVIEWER"));
	}

	private org.springframework.test.web.servlet.request.RequestPostProcessor adminJwt(String subject) {
		return jwt()
			.jwt(token -> token.subject(subject).claim("roles", List.of("SUPPORT_ADMIN")))
			.authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_ADMIN"));
	}

	private String createTicket(String subject, String traceId) throws Exception {
		var response = mockMvc.perform(post("/api/tickets")
				.with(agentJwt(subject))
				.header("X-Trace-Id", traceId)
				.contentType(APPLICATION_JSON)
				.content("""
					{
					  "channel": "EMAIL",
					  "customerName": "Audit Test Customer",
					  "customerCompany": "Audit Test Company",
					  "customerTier": "STANDARD",
					  "subject": "Synthetic audit ticket",
					  "description": "Synthetic audit description"
					}
					"""))
			.andExpect(status().isCreated())
			.andReturn();
		return objectMapper.readTree(response.getResponse().getContentAsString()).get("id").asString();
	}

	private long auditCount() {
		return jdbcTemplate.queryForObject("select count(*) from audit_events", Long.class);
	}

	private void authenticate(String subject, String... roles) {
		var token = Jwt.withTokenValue("synthetic-audit-jwt")
			.header("alg", "none")
			.subject(subject)
			.build();
		var authorities = java.util.Arrays.stream(roles)
			.map(role -> new SimpleGrantedAuthority("ROLE_" + role))
			.toList();
		SecurityContextHolder.getContext().setAuthentication(new JwtAuthenticationToken(token, authorities));
	}
}
