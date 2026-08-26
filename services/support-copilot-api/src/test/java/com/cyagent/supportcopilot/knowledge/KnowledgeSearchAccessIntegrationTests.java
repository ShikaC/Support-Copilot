package com.cyagent.supportcopilot.knowledge;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import com.cyagent.supportcopilot.common.SyntheticJwt;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class KnowledgeSearchAccessIntegrationTests {

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private KnowledgeActiveReleaseRepository activeReleaseRepository;

	@Autowired
	private JdbcTemplate jdbcTemplate;

	@Value("${support-copilot.security.test-jwt-secret}")
	private String testJwtSecret;

	@AfterEach
	void restoreBaselineActiveRelease() {
		jdbcTemplate.update(
			"update knowledge_releases set allowed_scopes_json = ? where release_id = ?",
			"[\"GENERAL\",\"BILLING\",\"ACCOUNT\",\"PRIVACY\",\"TECHNICAL\"]",
			"support-copilot-bundled-v1"
		);
		if (!activeReleaseRepository.existsById(KnowledgeActiveRelease.SINGLETON_ID)) {
			activeReleaseRepository.saveAndFlush(new KnowledgeActiveRelease("support-copilot-bundled-v1"));
		}
	}

	@Test
	void missingTrustedScopesReturnNoKnowledgeDespiteBrowserScopeAndForbiddenIdHints() throws Exception {
		mockMvc.perform(get("/api/knowledge/search")
				.queryParam("query", "chunk-account-01 sso PRIVACY")
				.queryParam("topK", "10")
				.queryParam("support_scopes", "ACCOUNT,PRIVACY")
				.header("X-Support-Scopes", "ACCOUNT,PRIVACY")
				.header("Authorization", "Bearer " + SyntheticJwt.signed(
					testJwtSecret,
					"SUPPORT_AGENT",
					"missing-scope-agent"
				)))
			.andExpect(status().isOk())
			.andExpect(content().json("[]"));
	}

	@ParameterizedTest
	@CsvSource({
		"GENERAL,chunk-payment-04",
		"BILLING,chunk-billing-07",
		"ACCOUNT,chunk-account-01",
		"PRIVACY,chunk-privacy-03",
		"TECHNICAL,chunk-sync-2047"
	})
	void trustedScopeCanOnlySearchItsCatalogEntriesDespiteCollidingBrowserHints(
		String trustedScope,
		String expectedChunkId
	) throws Exception {
		mockMvc.perform(get("/api/knowledge/search")
				.queryParam("query", "chunk-billing-07 chunk-payment-04 chunk-account-01 chunk-privacy-03 chunk-sync-2047")
				.queryParam("topK", "10")
				.queryParam("support_scopes", "GENERAL,BILLING,ACCOUNT,PRIVACY,TECHNICAL")
				.header("X-Support-Scopes", "GENERAL,BILLING,ACCOUNT,PRIVACY,TECHNICAL")
				.header("Authorization", "Bearer " + scopedAgentToken(trustedScope)))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$").isArray())
			.andExpect(jsonPath("$.length()").value(1))
			.andExpect(jsonPath("$[0].chunkId").value(expectedChunkId));
	}

	@Test
	void activeReleaseScopeIntersectionCanDenyAnOtherwiseTrustedCatalogScope() throws Exception {
		jdbcTemplate.update(
			"update knowledge_releases set allowed_scopes_json = ? where release_id = ?",
			"[\"GENERAL\"]",
			"support-copilot-bundled-v1"
		);

		mockMvc.perform(get("/api/knowledge/search")
				.queryParam("query", "chunk-billing-07")
				.header("Authorization", "Bearer " + scopedAgentToken("BILLING")))
			.andExpect(status().isOk())
			.andExpect(content().json("[]"));
	}

	@Test
	void unauthenticatedKnowledgeSearchReturnsUnauthorized() throws Exception {
		mockMvc.perform(get("/api/knowledge/search").queryParam("query", "chunk-account-01"))
			.andExpect(status().isUnauthorized());
	}

	@Test
	void unavailableActiveReleaseFailsClosedWithTheExistingKnowledgeAccessError() throws Exception {
		activeReleaseRepository.deleteById(KnowledgeActiveRelease.SINGLETON_ID);
		activeReleaseRepository.flush();

		mockMvc.perform(get("/api/knowledge/search")
				.queryParam("query", "chunk-account-01")
				.header("Authorization", "Bearer " + scopedAgentToken("ACCOUNT")))
			.andExpect(status().isConflict())
			.andExpect(jsonPath("$.code").value("KNOWLEDGE_RELEASE_INACTIVE"))
			.andExpect(content().string(org.hamcrest.Matchers.not(
				org.hamcrest.Matchers.containsString("chunk-account-01")
			)));
	}

	private String scopedAgentToken(String scope) throws Exception {
		return SyntheticJwt.signed(
			testJwtSecret,
			"SUPPORT_AGENT",
			"scoped-agent-" + scope.toLowerCase(),
			Map.of("support_scopes", List.of(scope))
		);
	}
}
