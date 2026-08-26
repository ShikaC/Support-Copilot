package com.cyagent.supportcopilot.analysis.review;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.http.MediaType.APPLICATION_JSON;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.List;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
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

import com.cyagent.supportcopilot.analysis.AnalysisPersistenceService;
import com.cyagent.supportcopilot.analysis.AnalysisRunRepository;
import com.cyagent.supportcopilot.analysis.MockAnalysisFactory;
import com.cyagent.supportcopilot.ticket.TicketRepository;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class ReviewActorIdentityContractTests {

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

	@Value("${support-copilot.security.test-jwt-secret}")
	private String testJwtSecret;

	private String ticketId;

	@AfterEach
	void cleanUp() {
		if (ticketId != null) {
			analysisReviewRepository.deleteAllByTicketId(ticketId);
			analysisRunRepository.findByTicketIdOrderByCreatedAtDesc(ticketId)
				.forEach(analysisRunRepository::delete);
			ticketRepository.deleteById(ticketId);
		}
	}

	@ParameterizedTest
	@CsvSource(value = {
		"missing-reviewer,SUPPORT_REVIEWER,<missing>",
		"missing-admin,SUPPORT_ADMIN,<missing>",
		"empty-reviewer,SUPPORT_REVIEWER,''",
		"empty-admin,SUPPORT_ADMIN,''",
		"whitespace-reviewer,SUPPORT_REVIEWER,'   '",
		"whitespace-admin,SUPPORT_ADMIN,'   '"
	}, nullValues = "<missing>", ignoreLeadingAndTrailingWhitespace = false)
	void signedReviewRoleWithoutUsableSubjectCannotCreateReview(
		String scenario,
		String role,
		String subject
	) throws Exception {
		var analysisId = saveReviewableAnalysis();
		var traceId = "trace-" + scenario;

		mockMvc.perform(post(reviewPath(analysisId))
				.header("Authorization", "Bearer " + signedJwt(role, subject))
				.header("X-Trace-Id", traceId)
				.header("X-Review-Actor", "spoofed-browser-actor")
				.contentType(APPLICATION_JSON)
				.content("{\"replyContent\":\"Synthetic reviewed reply.\"}"))
			.andExpect(status().isForbidden())
			.andExpect(header().string("X-Trace-Id", traceId))
			.andExpect(jsonPath("$.code").value("ACCESS_DENIED"))
			.andExpect(jsonPath("$.traceId").value(traceId));

		assertThat(analysisReviewRepository.findByAnalysisIdOrderByCreatedAtDesc(analysisId))
			.isEmpty();
	}

	@Test
	void signedReviewRoleWithNonBlankSubjectPersistsTrustedActor() throws Exception {
		var analysisId = saveReviewableAnalysis();

		mockMvc.perform(post(reviewPath(analysisId))
				.header("Authorization", "Bearer " + signedJwt(
					"SUPPORT_REVIEWER",
					"trusted-reviewer-control"
				))
				.header("X-Review-Actor", "spoofed-browser-actor")
				.contentType(APPLICATION_JSON)
				.content("{\"replyContent\":\"Synthetic reviewed reply.\"}"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.reviewerLabel").value("trusted-reviewer-control"));

		var persisted = analysisReviewRepository.findFirstByAnalysisIdOrderByCreatedAtDesc(analysisId)
			.orElseThrow();
		assertThat(persisted.getReviewerLabel()).isEqualTo("trusted-reviewer-control");
		assertThat(persisted.getReviewerLabel()).isNotEqualTo("spoofed-browser-actor");
	}

	private String signedJwt(String role, String subject) throws Exception {
		var now = Instant.now();
		var claims = new JWTClaimsSet.Builder()
			.issueTime(Date.from(now))
			.expirationTime(Date.from(now.plus(Duration.ofMinutes(5))))
			.claim("roles", List.of(role));
		if (subject != null) {
			claims.subject(subject);
		}
		var jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), claims.build());
		jwt.sign(new MACSigner(testJwtSecret.getBytes(StandardCharsets.UTF_8)));
		return jwt.serialize();
	}

	private String saveReviewableAnalysis() {
		var ticket = AnalysisReviewTestFixture.ticket();
		ticketId = ticket.getId();
		ticketRepository.saveAndFlush(ticket);
		var analysis = mockAnalysisFactory.createMock(ticket);
		analysisPersistenceService.persist(ticket.getId(), ticket.getVersion(), analysis);
		return analysis.id();
	}

	private String reviewPath(String analysisId) {
		return "/api/tickets/" + ticketId + "/analyses/" + analysisId + "/reviews";
	}
}
