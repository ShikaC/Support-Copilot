package com.cyagent.supportcopilot.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.http.MediaType.APPLICATION_JSON;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Duration;
import java.time.Instant;
import java.util.UUID;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

import com.cyagent.supportcopilot.analysis.AnalysisPersistenceService;
import com.cyagent.supportcopilot.analysis.AnalysisRunRepository;
import com.cyagent.supportcopilot.analysis.MockAnalysisFactory;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewRepository;
import com.cyagent.supportcopilot.common.SyntheticJwt;
import com.cyagent.supportcopilot.ticket.Ticket;
import com.cyagent.supportcopilot.ticket.TicketRepository;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class PilotSecurityContractTests {

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private TicketRepository ticketRepository;

	@Autowired
	private AnalysisRunRepository analysisRunRepository;

	@Autowired
	private AnalysisReviewRepository analysisReviewRepository;

	@Autowired
	private MockAnalysisFactory mockAnalysisFactory;

	@Autowired
	private AnalysisPersistenceService analysisPersistenceService;

	@Autowired
	private JdbcTemplate jdbcTemplate;

	private String ticketId;

	@Value("${support-copilot.security.test-jwt-secret}")
	private String testJwtSecret;

	@AfterEach
	void cleanUp() {
		jdbcTemplate.update("delete from audit_events");
		if (ticketId != null) {
			analysisReviewRepository.deleteAllByTicketId(ticketId);
			analysisRunRepository.findByTicketIdOrderByCreatedAtDesc(ticketId)
				.forEach(analysisRunRepository::delete);
			ticketRepository.deleteById(ticketId);
		}
	}

	@Test
	void anonymousBusinessRequestReturnsStableTraceableUnauthorizedJson() throws Exception {
		mockMvc.perform(get("/api/tickets").header("X-Trace-Id", "trace-anonymous"))
			.andExpect(status().isUnauthorized())
			.andExpect(header().string("X-Trace-Id", "trace-anonymous"))
			.andExpect(jsonPath("$.code").value("AUTHENTICATION_REQUIRED"))
			.andExpect(jsonPath("$.message").isString())
			.andExpect(jsonPath("$.traceId").value("trace-anonymous"))
			.andExpect(content().string(org.hamcrest.Matchers.not(
				org.hamcrest.Matchers.containsString("Bearer")
			)));
	}

	@Test
	void malformedBearerTokenReturnsUnauthorizedWithoutCredentialEcho() throws Exception {
		mockMvc.perform(get("/api/tickets")
				.header("Authorization", "Bearer malformed-test-value")
				.header("X-Trace-Id", "trace-malformed"))
			.andExpect(status().isUnauthorized())
			.andExpect(jsonPath("$.code").value("AUTHENTICATION_REQUIRED"))
			.andExpect(jsonPath("$.traceId").value("trace-malformed"))
			.andExpect(content().string(org.hamcrest.Matchers.not(
				org.hamcrest.Matchers.containsString("malformed-test-value")
			)));
	}

	@Test
	void authenticatedWrongRoleReturnsStableForbiddenJson() throws Exception {
		mockMvc.perform(get("/api/tickets")
				.header("Authorization", "Bearer " + signedJwt("CUSTOMER", "customer-subject"))
				.header("X-Trace-Id", "trace-forbidden"))
			.andExpect(status().isForbidden())
			.andExpect(jsonPath("$.code").value("ACCESS_DENIED"))
			.andExpect(jsonPath("$.message").isString())
			.andExpect(jsonPath("$.traceId").value("trace-forbidden"));
	}

	@Test
	void explicitTestDecoderMapsSignedRolesClaim() throws Exception {
		mockMvc.perform(get("/api/tickets")
				.header("Authorization", "Bearer " + signedJwt("SUPPORT_AGENT", "signed-agent-subject")))
			.andExpect(status().isOk());
	}

	@ParameterizedTest
	@CsvSource({
		"SUPPORT_AGENT,/api/tickets",
		"SUPPORT_AGENT,/api/knowledge/search?query=sso",
		"SUPPORT_AGENT,/api/metrics",
		"SUPPORT_REVIEWER,/api/tickets",
		"SUPPORT_REVIEWER,/api/knowledge/search?query=sso",
		"SUPPORT_REVIEWER,/api/metrics",
		"SUPPORT_ADMIN,/api/tickets",
		"SUPPORT_ADMIN,/api/knowledge/search?query=sso",
		"SUPPORT_ADMIN,/api/metrics"
	})
	void supportRolesCanReadAgentBusinessEndpoints(String role, String endpoint) throws Exception {
		mockMvc.perform(get(endpoint)
				.header("Authorization", "Bearer " + signedJwt(role, role.toLowerCase())))
			.andExpect(status().isOk());
	}

	@Test
	void agentCannotReadReviews() throws Exception {
		var analysisId = saveReviewableAnalysis();

		mockMvc.perform(get(reviewPath(analysisId))
				.header("Authorization", "Bearer " + signedJwt("SUPPORT_AGENT", "agent-subject")))
			.andExpect(status().isForbidden());
	}

	@ParameterizedTest
	@CsvSource({"SUPPORT_REVIEWER,reviewer-subject", "SUPPORT_ADMIN,admin-subject"})
	void reviewerAndAdminCanReadReviews(String role, String subject) throws Exception {
		var analysisId = saveReviewableAnalysis();

		mockMvc.perform(get(reviewPath(analysisId))
				.header("Authorization", "Bearer " + signedJwt(role, subject)))
			.andExpect(status().isOk());
	}

	@Test
	void reviewActorComesFromJwtSubjectAndIgnoresSpoofingHeader() throws Exception {
		var analysisId = saveReviewableAnalysis();

		mockMvc.perform(post(reviewPath(analysisId))
				.header("Authorization", "Bearer " + signedJwt("SUPPORT_REVIEWER", "trusted-reviewer-subject"))
				.header("Idempotency-Key", "pilot-review-actor-key-0001")
				.header("X-Review-Actor", "spoofed-browser-actor")
				.contentType(APPLICATION_JSON)
				.content("{\"replyContent\":\"请按知识步骤核验。\"}"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.reviewerType").value("AUTHENTICATED_JWT"))
			.andExpect(jsonPath("$.reviewerLabel").value("trusted-reviewer-subject"));

		var persisted = analysisReviewRepository.findFirstByAnalysisIdOrderByCreatedAtDesc(analysisId)
			.orElseThrow();
		assertThat(persisted.getReviewerLabel()).isEqualTo("trusted-reviewer-subject");
		assertThat(persisted.getReviewerLabel()).isNotEqualTo("spoofed-browser-actor");
	}

	@Test
	void onlyAdminCanReadNonHealthActuatorEndpoints() throws Exception {
		mockMvc.perform(get("/actuator/info")
				.header("Authorization", "Bearer " + signedJwt("SUPPORT_AGENT", "agent-subject")))
			.andExpect(status().isForbidden());
		mockMvc.perform(get("/actuator/info")
				.header("Authorization", "Bearer " + signedJwt("SUPPORT_ADMIN", "admin-subject")))
			.andExpect(status().isOk());
	}

	@Test
	void healthIsPublicAndMinimal() throws Exception {
		mockMvc.perform(get("/actuator/health"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.status").value("UP"))
			.andExpect(jsonPath("$.groups").isArray())
			.andExpect(jsonPath("$.components").doesNotExist())
			.andExpect(jsonPath("$.details").doesNotExist());
	}

	@ParameterizedTest
	@org.junit.jupiter.params.provider.ValueSource(strings = {
		"/actuator/health/liveness",
		"/actuator/health/readiness"
	})
	void healthProbesArePublicAndMinimal(String endpoint) throws Exception {
		mockMvc.perform(get(endpoint))
			.andExpect(status().isOk())
			.andExpect(content().string("{\"status\":\"UP\"}"));
	}

	@Test
	void corsPreflightDoesNotOpenTheBusinessRequest() throws Exception {
		mockMvc.perform(options("/api/tickets")
				.header("Origin", "http://localhost:5173")
				.header("Access-Control-Request-Method", "GET"))
			.andExpect(status().isOk());
		mockMvc.perform(get("/api/tickets").header("Origin", "http://localhost:5173"))
			.andExpect(status().isUnauthorized());
	}

	@Test
	void authorizedStaleWritePreservesCanonicalConflictAndTraceId() throws Exception {
		var ticket = saveTicket();

		mockMvc.perform(patch("/api/tickets/{id}", ticket.getId())
				.header("Authorization", "Bearer " + signedJwt("SUPPORT_AGENT", "agent-subject"))
				.header("X-Trace-Id", "trace-authorized-conflict")
				.contentType(APPLICATION_JSON)
				.content("{\"priority\":\"HIGH\",\"expectedVersion\":99}"))
			.andExpect(status().isConflict())
			.andExpect(jsonPath("$.code").value("VERSION_CONFLICT"))
			.andExpect(jsonPath("$.traceId").value("trace-authorized-conflict"));
	}

	private String signedJwt(String role, String subject) throws Exception {
		return SyntheticJwt.signed(testJwtSecret, role, subject);
	}

	private String reviewPath(String analysisId) {
		return "/api/tickets/" + ticketId + "/analyses/" + analysisId + "/reviews";
	}

	private String saveReviewableAnalysis() {
		var ticket = saveTicket();
		var analysis = mockAnalysisFactory.createMock(ticket);
		var jwt = Jwt.withTokenValue("synthetic-security-fixture-jwt")
			.header("alg", "none")
			.subject("security-fixture-agent")
			.build();
		SecurityContextHolder.getContext().setAuthentication(new JwtAuthenticationToken(
			jwt,
			java.util.List.of(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT"))
		));
		try {
			analysisPersistenceService.persist(ticket.getId(), ticket.getVersion(), analysis);
		} finally {
			SecurityContextHolder.clearContext();
		}
		return analysis.id();
	}

	private Ticket saveTicket() {
		var now = Instant.now();
		var ticket = new Ticket();
		ticketId = "ticket-sec-" + UUID.randomUUID().toString().substring(0, 12);
		ticket.setId(ticketId);
		ticket.setTicketNo("SC-SEC-" + UUID.randomUUID().toString().substring(0, 8));
		ticket.setChannel("EMAIL");
		ticket.setCustomerName("安全契约客户");
		ticket.setCustomerCompany("安全契约公司");
		ticket.setCustomerTier("STANDARD");
		ticket.setSubject("安全契约测试");
		ticket.setDescription("使用合成数据验证认证授权边界。");
		ticket.setLanguage("zh-CN");
		ticket.setCategory("ACCOUNT_ACCESS");
		ticket.setPriority("MEDIUM");
		ticket.setStatus("NEW");
		ticket.setSlaDeadline(now.plus(Duration.ofHours(8)));
		ticket.setCreatedAt(now);
		ticket.setUpdatedAt(now);
		return ticketRepository.saveAndFlush(ticket);
	}
}
