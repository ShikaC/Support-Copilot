package com.cyagent.supportcopilot.knowledge;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.http.MediaType.APPLICATION_JSON;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.List;

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
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

import tools.jackson.databind.ObjectMapper;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_CLASS)
class KnowledgeReleaseIntegrationTests {

	private static final String CHECKSUM_A = "a".repeat(64);
	private static final String CHECKSUM_B = "b".repeat(64);

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private ObjectMapper objectMapper;

	@Autowired
	private JdbcTemplate jdbcTemplate;

	@AfterEach
	void cleanUp() {
		jdbcTemplate.update("delete from audit_events where target_type = 'KNOWLEDGE_RELEASE'");
		jdbcTemplate.update("delete from knowledge_active_release");
		jdbcTemplate.update("delete from knowledge_releases");
	}

	@Test
	void releaseRoutesEnforceAuthenticationAndReviewerMutationRoles() throws Exception {
		mockMvc.perform(get("/api/knowledge/releases"))
			.andExpect(status().isUnauthorized());
		mockMvc.perform(post("/api/knowledge/releases")
				.with(agent("agent-subject"))
				.contentType(APPLICATION_JSON)
				.content(draftJson("release-role", 9, CHECKSUM_A, List.of("GENERAL"))))
			.andExpect(status().isForbidden());
		mockMvc.perform(post("/api/knowledge/releases")
				.with(reviewer("reviewer-subject"))
				.contentType(APPLICATION_JSON)
				.content(draftJson("release-role", 9, CHECKSUM_A, List.of("GENERAL"))))
			.andExpect(status().isCreated())
			.andExpect(jsonPath("$.releaseId").value("release-role"));
	}

	@Test
	void createApprovePublishAndRollbackAreImmutableAtomicAndAudited() throws Exception {
		createDraft("release-a", 2, CHECKSUM_A, List.of("GENERAL", "BILLING"), "trusted-reviewer");
		approve("release-a", 0, "trusted-reviewer")
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.status").value("APPROVED"))
			.andExpect(jsonPath("$.version").value(1));
		publish("release-a", 1, "trusted-admin")
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.status").value("PUBLISHED"));

		createDraft("release-b", 3, CHECKSUM_B, List.of("TECHNICAL", "PRIVACY"), "trusted-reviewer");
		approve("release-b", 0, "trusted-reviewer").andExpect(status().isOk());
		publish("release-b", 1, "trusted-admin").andExpect(status().isOk());

		mockMvc.perform(get("/api/knowledge/releases/active").with(agent("agent-subject")))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.releaseId").value("release-b"))
			.andExpect(jsonPath("$.corpusChecksum").value(CHECKSUM_B));
		mockMvc.perform(post("/api/knowledge/releases/release-a/rollback")
				.with(admin("rollback-admin"))
				.contentType(APPLICATION_JSON)
				.content("{\"expectedVersion\":3}"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.releaseId").value("release-a"))
			.andExpect(jsonPath("$.status").value("PUBLISHED"));

		var releaseA = jdbcTemplate.queryForMap(
			"select release_version, corpus_checksum, allowed_scopes_json from knowledge_releases where release_id = ?",
			"release-a"
		);
		assertThat(releaseA.get("RELEASE_VERSION")).isEqualTo(2);
		assertThat(releaseA.get("CORPUS_CHECKSUM")).isEqualTo(CHECKSUM_A);
		assertThat(releaseA.get("ALLOWED_SCOPES_JSON").toString()).isEqualTo("[\"GENERAL\",\"BILLING\"]");

		var events = jdbcTemplate.queryForList(
			"select actor_subject, action, metadata_json from audit_events where target_type = 'KNOWLEDGE_RELEASE' order by created_at"
		);
		assertThat(events).hasSize(7);
		assertThat(events).extracting(row -> row.get("ACTION")).containsExactly(
			"KNOWLEDGE_RELEASE_DRAFT_CREATED",
			"KNOWLEDGE_RELEASE_APPROVED",
			"KNOWLEDGE_RELEASE_PUBLISHED",
			"KNOWLEDGE_RELEASE_DRAFT_CREATED",
			"KNOWLEDGE_RELEASE_APPROVED",
			"KNOWLEDGE_RELEASE_PUBLISHED",
			"KNOWLEDGE_RELEASE_ROLLED_BACK"
		);
		assertThat(events.getLast().get("ACTOR_SUBJECT")).isEqualTo("rollback-admin");
		assertThat(events.toString()).contains("release-a", CHECKSUM_A, "GENERAL", "BILLING")
			.doesNotContain("raw customer", "Authorization");
	}

	@Test
	void duplicateReleaseVersionCannotReplacePublishedRelease() throws Exception {
		createDraft("release-version-owner", 20, CHECKSUM_A, List.of("GENERAL"), "trusted-reviewer");
		approve("release-version-owner", 0, "trusted-reviewer").andExpect(status().isOk());
		publish("release-version-owner", 1, "trusted-admin").andExpect(status().isOk());
		var auditCount = knowledgeAuditCount();

		mockMvc.perform(post("/api/knowledge/releases")
				.with(reviewer("trusted-reviewer"))
				.contentType(APPLICATION_JSON)
				.content(draftJson("release-conflicting-candidate", 20, CHECKSUM_B, List.of("GENERAL"))))
			.andExpect(status().isBadRequest());

		mockMvc.perform(get("/api/knowledge/releases/active").with(agent("agent-subject")))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.releaseId").value("release-version-owner"))
			.andExpect(jsonPath("$.corpusChecksum").value(CHECKSUM_A))
			.andExpect(jsonPath("$.status").value("PUBLISHED"));
		assertThat(jdbcTemplate.queryForObject(
			"select count(*) from knowledge_releases where release_id = 'release-conflicting-candidate'",
			Long.class
		)).isZero();
		assertThat(knowledgeAuditCount()).isEqualTo(auditCount);
	}

	@Test
	void staleIllegalMissingAndInvalidRequestsReturnStableErrorsWithoutAudit() throws Exception {
		createDraft("release-errors", 4, CHECKSUM_A, List.of(), "trusted-reviewer");
		var initialAuditCount = knowledgeAuditCount();

		approve("release-errors", 9, "trusted-reviewer")
			.andExpect(status().isConflict())
			.andExpect(jsonPath("$.code").value("KNOWLEDGE_RELEASE_VERSION_CONFLICT"));
		publish("release-errors", 0, "trusted-admin")
			.andExpect(status().isConflict())
			.andExpect(jsonPath("$.code").value("KNOWLEDGE_RELEASE_ILLEGAL_TRANSITION"));
		approve("missing-release", 0, "trusted-reviewer")
			.andExpect(status().isNotFound())
			.andExpect(jsonPath("$.code").value("KNOWLEDGE_RELEASE_NOT_FOUND"));
		mockMvc.perform(post("/api/knowledge/releases")
				.with(reviewer("trusted-reviewer"))
				.contentType(APPLICATION_JSON)
				.content(draftJson("bad-release", 5, "ABC", List.of("GENERAL"))))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.code").value("INVALID_KNOWLEDGE_CHECKSUM"));
		mockMvc.perform(post("/api/knowledge/releases")
				.with(reviewer("trusted-reviewer"))
				.contentType(APPLICATION_JSON)
				.content(draftJson("bad-scope", 5, CHECKSUM_B, List.of("SUPERUSER"))))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.code").value("INVALID_KNOWLEDGE_SCOPE"));

		assertThat(knowledgeAuditCount()).isEqualTo(initialAuditCount);
		assertThat(jdbcTemplate.queryForObject(
			"select status from knowledge_releases where release_id = 'release-errors'",
			String.class
		)).isEqualTo("DRAFT");
	}

	@Test
	void rollbackAuditFailureLeavesActivePointerAndReleaseStatesUnchangedWithNoEvent() throws Exception {
		createDraft("release-stable", 6, CHECKSUM_A, List.of("GENERAL"), "trusted-reviewer");
		approve("release-stable", 0, "trusted-reviewer").andExpect(status().isOk());
		publish("release-stable", 1, "trusted-admin").andExpect(status().isOk());
		createDraft("release-current", 7, CHECKSUM_B, List.of("BILLING"), "trusted-reviewer");
		approve("release-current", 0, "trusted-reviewer").andExpect(status().isOk());
		publish("release-current", 1, "trusted-admin").andExpect(status().isOk());
		var auditCount = knowledgeAuditCount();

		var jwt = Jwt.withTokenValue("synthetic-rollback-failure-jwt")
			.header("alg", "none")
			.subject("x".repeat(140))
			.build();
		SecurityContextHolder.getContext().setAuthentication(new JwtAuthenticationToken(
			jwt,
			List.of(new SimpleGrantedAuthority("ROLE_SUPPORT_ADMIN"))
		));
		try {
			assertThatThrownBy(() -> service().rollback("release-stable", 3))
				.isInstanceOf(RuntimeException.class);
		} finally {
			SecurityContextHolder.clearContext();
		}

		assertThat(knowledgeAuditCount()).isEqualTo(auditCount);
		assertThat(jdbcTemplate.queryForObject(
			"select release_id from knowledge_active_release where id = 'active'",
			String.class
		)).isEqualTo("release-current");
		assertThat(jdbcTemplate.queryForObject(
			"select status from knowledge_releases where release_id = 'release-stable'",
			String.class
		)).isEqualTo("ARCHIVED");
	}

	@Autowired
	private KnowledgeReleaseService knowledgeReleaseService;

	private KnowledgeReleaseService service() {
		return knowledgeReleaseService;
	}

	private void createDraft(
		String releaseId,
		int releaseVersion,
		String checksum,
		List<String> scopes,
		String actor
	) throws Exception {
		mockMvc.perform(post("/api/knowledge/releases")
				.with(reviewer(actor))
				.header("X-Actor", "spoofed-browser-actor")
				.contentType(APPLICATION_JSON)
				.content(draftJson(releaseId, releaseVersion, checksum, scopes)))
			.andExpect(status().isCreated())
			.andExpect(jsonPath("$.status").value("DRAFT"))
			.andExpect(jsonPath("$.version").value(0));
	}

	private org.springframework.test.web.servlet.ResultActions approve(
		String releaseId,
		long expectedVersion,
		String actor
	) throws Exception {
		return mockMvc.perform(post("/api/knowledge/releases/{releaseId}/approve", releaseId)
			.with(reviewer(actor))
			.contentType(APPLICATION_JSON)
			.content("{\"expectedVersion\":" + expectedVersion + "}"));
	}

	private org.springframework.test.web.servlet.ResultActions publish(
		String releaseId,
		long expectedVersion,
		String actor
	) throws Exception {
		return mockMvc.perform(post("/api/knowledge/releases/{releaseId}/publish", releaseId)
			.with(admin(actor))
			.contentType(APPLICATION_JSON)
			.content("{\"expectedVersion\":" + expectedVersion + "}"));
	}

	private String draftJson(String releaseId, int releaseVersion, String checksum, List<String> scopes)
		throws Exception {
		return objectMapper.writeValueAsString(java.util.Map.of(
			"releaseId", releaseId,
			"releaseVersion", releaseVersion,
			"corpusChecksum", checksum,
			"allowedScopes", scopes
		));
	}

	private long knowledgeAuditCount() {
		return jdbcTemplate.queryForObject(
			"select count(*) from audit_events where target_type = 'KNOWLEDGE_RELEASE'",
			Long.class
		);
	}

	private RequestPostProcessor agent(String subject) {
		return jwt().jwt(token -> token.subject(subject).claim("roles", List.of("SUPPORT_AGENT")))
			.authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT"));
	}

	private RequestPostProcessor reviewer(String subject) {
		return jwt().jwt(token -> token.subject(subject).claim("roles", List.of("SUPPORT_REVIEWER")))
			.authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_REVIEWER"));
	}

	private RequestPostProcessor admin(String subject) {
		return jwt().jwt(token -> token.subject(subject).claim("roles", List.of("SUPPORT_ADMIN")))
			.authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_ADMIN"));
	}
}
