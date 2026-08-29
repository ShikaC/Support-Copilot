package com.cyagent.supportcopilot.config;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import com.cyagent.supportcopilot.common.SyntheticJwt;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class JwtClaimValidationIntegrationTests {

	@Autowired
	private MockMvc mockMvc;

	@Value("${support-copilot.security.test-jwt-secret}")
	private String testJwtSecret;

	@Test
	void signedSupportAgentRetainsAuthorizedOutcome() throws Exception {
		mockMvc.perform(get("/api/tickets")
				.header("Authorization", "Bearer " + signedJwt("baseline-agent-subject")))
			.andExpect(status().isOk());
	}

	@Test
	void signedTokenWithWrongAudienceIsUnauthorized() throws Exception {
		var token = SyntheticJwt.signed(
			testJwtSecret,
			"SUPPORT_AGENT",
			"wrong-audience-subject",
			Map.of("aud", List.of("another-api"))
		);

		mockMvc.perform(get("/api/tickets")
				.header("Authorization", "Bearer " + token))
			.andExpect(status().isUnauthorized());
	}

	@Test
	void signedTokenWithoutAudienceIsUnauthorized() throws Exception {
		var token = SyntheticJwt.signedWithoutAudience(
			testJwtSecret,
			"SUPPORT_AGENT",
			"missing-audience-subject"
		);

		mockMvc.perform(get("/api/tickets")
				.header("Authorization", "Bearer " + token))
			.andExpect(status().isUnauthorized());
	}

	@Test
	void signedTokenWithWrongIssuerIsUnauthorized() throws Exception {
		var token = SyntheticJwt.signed(
			testJwtSecret,
			"SUPPORT_AGENT",
			"wrong-issuer-subject",
			Map.of("iss", "https://untrusted-issuer.test")
		);

		mockMvc.perform(get("/api/tickets")
				.header("Authorization", "Bearer " + token))
			.andExpect(status().isUnauthorized());
	}

	private String signedJwt(String subject) throws Exception {
		return SyntheticJwt.signed(testJwtSecret, "SUPPORT_AGENT", subject);
	}
}
