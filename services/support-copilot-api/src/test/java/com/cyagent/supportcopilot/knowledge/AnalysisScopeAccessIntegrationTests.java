package com.cyagent.supportcopilot.knowledge;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import com.cyagent.supportcopilot.analysis.AnalysisResponse;
import com.cyagent.supportcopilot.analysis.AnalysisRun;
import com.cyagent.supportcopilot.analysis.AnalysisRunRepository;
import com.cyagent.supportcopilot.analysis.MockAnalysisFactory;
import com.cyagent.supportcopilot.common.SyntheticJwt;
import com.cyagent.supportcopilot.ticket.Ticket;
import com.cyagent.supportcopilot.ticket.TicketRepository;
import tools.jackson.databind.ObjectMapper;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
class AnalysisScopeAccessIntegrationTests {
	@Autowired MockMvc mvc;
	@Autowired TicketRepository tickets;
	@Autowired AnalysisRunRepository runs;
	@Autowired ObjectMapper mapper;
	@Autowired MockAnalysisFactory factory;
	@Autowired KnowledgeCorpusStore corpus;
	@Autowired com.cyagent.supportcopilot.analysis.review.AnalysisReviewRepository reviews;
	@Value("${support-copilot.security.test-jwt-secret}") String secret;

	@Test
	void noScopeCallerCannotReadPersistedBillingAnalysisViaHistoryDetailOrList() throws Exception {
		var ticket = saveAnalysis(false);
		var token = token(List.of());
		var search = mvc.perform(get("/api/knowledge/search").param("query", "chunk-billing-07")
			.header("Authorization", token)).andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
		assertThat(search).isEqualTo("[]");
		for (var path : List.of("/api/tickets/" + ticket.getId() + "/analyses", "/api/tickets/" + ticket.getId(), "/api/tickets")) {
			var result = mvc.perform(get(path).header("Authorization", token))
				.andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
			assertThat(result).doesNotContain("chunk-billing-07", "restricted-generated-reply");
		}
	}

	@Test
	void billingCallerCanReadCurrentCanonicalEvidence() throws Exception {
		var ticket = saveAnalysis(false);
		var result = mvc.perform(get("/api/tickets/" + ticket.getId() + "/analyses")
			.header("Authorization", token(List.of("BILLING"))))
			.andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
		assertThat(result).contains("chunk-billing-07", "restricted-generated-reply");
	}

	@Test
	void changedHistoricalChunkFailsClosedEvenForBillingCaller() throws Exception {
		var ticket = saveAnalysis(true);
		var result = mvc.perform(get("/api/tickets/" + ticket.getId() + "/analyses")
			.header("Authorization", token(List.of("BILLING"))))
			.andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
		assertThat(result).isEqualTo("[]");
	}

	@Test
	void noScopeReviewerCannotReadOrCreateReviewOfRestrictedAnalysis() throws Exception {
		var ticket = saveAnalysis(false);
		var run = runs.findFirstByTicketIdOrderByCreatedAtDesc(ticket.getId()).orElseThrow();
		var review = new com.cyagent.supportcopilot.analysis.review.AnalysisReview();
		review.setId("review-scope-probe"); review.setTicketId(ticket.getId()); review.setAnalysisId(run.getId());
		review.setAction(com.cyagent.supportcopilot.analysis.review.AnalysisReviewAction.EDITED);
		review.setReviewerType("AUTHENTICATED_JWT"); review.setReviewerLabel("billing-reviewer");
		review.setOriginalReplyContent("restricted-generated-reply"); review.setReviewedReplyContent("restricted-reviewed-reply");
		review.setTicketVersion(0); review.setTraceId(run.getTraceId()); review.setCreatedAt(Instant.now());
		reviews.saveAndFlush(review);
		var token = "Bearer " + SyntheticJwt.signed(secret, "SUPPORT_REVIEWER", "no-scope-reviewer");
		var path = "/api/tickets/" + ticket.getId() + "/analyses/" + run.getId() + "/reviews";
		mvc.perform(get(path).header("Authorization", token)).andExpect(status().isForbidden());
		mvc.perform(post(path).header("Authorization", token).header("Idempotency-Key", "scope-review-probe-0001")
			.contentType("application/json").content("{\"replyContent\":\"reviewed\"}"))
			.andExpect(status().isForbidden());
		var detail = mvc.perform(get("/api/tickets/" + ticket.getId()).header("Authorization", token))
			.andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
		assertThat(detail).doesNotContain("restricted-generated-reply", "restricted-reviewed-reply");
	}

	private String token(List<String> scopes) throws Exception {
		return "Bearer " + SyntheticJwt.signed(secret, "SUPPORT_AGENT", "scope-bypass-probe", Map.of("support_scopes", scopes));
	}

	private Ticket saveAnalysis(boolean changedContent) {
		var ticket = new Ticket();
		ticket.setId("ticket-scope-probe"); ticket.setTicketNo("SC-SCOPE-PROBE");
		ticket.setChannel("EMAIL"); ticket.setCustomerName("Synthetic"); ticket.setCustomerCompany("Synthetic"); ticket.setCustomerTier("STANDARD");
		ticket.setSubject("Billing"); ticket.setDescription("Synthetic scope probe"); ticket.setLanguage("en");
		ticket.setCategory("BILLING"); ticket.setPriority("MEDIUM"); ticket.setStatus("NEW");
		var now = Instant.now(); ticket.setCreatedAt(now); ticket.setUpdatedAt(now); ticket.setSlaDeadline(now);
		tickets.saveAndFlush(ticket);
		var base = factory.createMock(ticket);
		var chunk = corpus.load().chunks().getFirst();
		var hit = new AnalysisResponse.RetrievalHit(chunk.chunkId(), chunk.documentId(), chunk.documentTitle(),
			chunk.section(), changedContent ? "restricted-old-content" : chunk.content(), chunk.sourceUri(), "HYBRID", 1, 1, 1, 1, true);
		var response = new AnalysisResponse(base.id(), base.traceId(), base.status(), base.mode(), base.fallbackReason(),
			base.modelName(), base.promptVersion(), base.classification(), base.workflowSteps(), new AnalysisResponse.Retrieval("billing", List.of(hit)),
			new AnalysisResponse.SuggestedReply("restricted-generated-reply", List.of(chunk.chunkId()), List.of()), base.decision(), base.usage(), base.createdAt());
		var run = new AnalysisRun();
		run.setId(response.id()); run.setTicketId(ticket.getId()); run.setSourceTicketVersion(ticket.getVersion());
		run.setTraceId(response.traceId()); run.setStatus(response.status()); run.setMode(response.mode());
		run.setResponseJson(mapper.writeValueAsString(response)); run.setCreatedAt(now); runs.saveAndFlush(run);
		return ticket;
	}
}
