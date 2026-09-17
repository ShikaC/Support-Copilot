package com.cyagent.supportcopilot.quality;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import com.cyagent.supportcopilot.common.SyntheticJwt;

@SpringBootTest(properties = {"quality.live-report-path=", "quality.live-report-sha256=",
	"quality.business-report-path=", "quality.business-report-sha256="})
@AutoConfigureMockMvc
@ActiveProfiles("test")
class QualityReportsSecurityTests {
	@Autowired MockMvc mvc;
	@Value("${support-copilot.security.test-jwt-secret}") String secret;

	@Test
	void anonymousAccessIsUnauthorized() throws Exception {
		mvc.perform(get("/api/quality-reports")).andExpect(status().isUnauthorized())
			.andExpect(jsonPath("$.code").value("AUTHENTICATION_REQUIRED"));
	}

	@Test
	void unrelatedRoleIsForbidden() throws Exception {
		mvc.perform(get("/api/quality-reports")
			.header("Authorization", "Bearer " + SyntheticJwt.signed(secret, "CUSTOMER", "customer")))
			.andExpect(status().isForbidden()).andExpect(jsonPath("$.code").value("ACCESS_DENIED"));
	}

	@ParameterizedTest
	@ValueSource(strings = {"SUPPORT_AGENT", "SUPPORT_REVIEWER", "SUPPORT_ADMIN"})
	void supportRolesReadIndependentSlots(String role) throws Exception {
		mvc.perform(get("/api/quality-reports")
			.header("Authorization", "Bearer " + SyntheticJwt.signed(secret, role, "reader")))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.liveEvaluation.status").value("NOT_CONFIGURED"))
			.andExpect(jsonPath("$.businessBenchmark.status").value("NOT_CONFIGURED"));
	}
}
