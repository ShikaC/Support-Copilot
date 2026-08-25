package com.cyagent.supportcopilot.analysis.review;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.http.MediaType.APPLICATION_JSON;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Instant;

import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import com.cyagent.supportcopilot.analysis.review.AnalysisReviewDtos.AnalysisReviewResponse;
import com.cyagent.supportcopilot.common.ApiExceptionHandler;

class AnalysisReviewApiTests {

	@Test
	void recordsReviewedReplyThroughExplicitCommand() throws Exception {
		var service = mock(AnalysisReviewService.class);
		var response = response("review-1", AnalysisReviewAction.EDITED, "修改后的回复");
		when(service.review("ticket-10042", "analysis-1", "修改后的回复")).thenReturn(response);

		mockMvc(service).perform(post("/api/tickets/ticket-10042/analyses/analysis-1/reviews")
				.contentType(APPLICATION_JSON)
				.content("{\"replyContent\":\"修改后的回复\"}"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.id").value("review-1"))
			.andExpect(jsonPath("$.action").value("EDITED"))
			.andExpect(jsonPath("$.reviewerType").value("UNAUTHENTICATED_DEMO"));

		verify(service).review("ticket-10042", "analysis-1", "修改后的回复");
	}

	@Test
	void returnsStructuredConflictForStaleAnalysisReview() throws Exception {
		var service = mock(AnalysisReviewService.class);
		when(service.review("ticket-10042", "analysis-old", "回复"))
			.thenThrow(new StaleAnalysisReviewException(
				"ticket-10042", "analysis-old", "analysis-latest", 4L, 5L
			));

		mockMvc(service).perform(post("/api/tickets/ticket-10042/analyses/analysis-old/reviews")
				.header("X-Trace-Id", "trace-review-conflict")
				.contentType(APPLICATION_JSON)
				.content("{\"replyContent\":\"回复\"}"))
			.andExpect(status().isConflict())
			.andExpect(jsonPath("$.code").value("ANALYSIS_REVIEW_STALE"))
			.andExpect(jsonPath("$.traceId").value("trace-review-conflict"))
			.andExpect(jsonPath("$.details.analysisId").value("analysis-old"))
			.andExpect(jsonPath("$.details.latestAnalysisId").value("analysis-latest"))
			.andExpect(jsonPath("$.details.currentTicketVersion").value(5));
	}

	private AnalysisReviewResponse response(
		String id,
		AnalysisReviewAction action,
		String reviewedReply
	) {
		return new AnalysisReviewResponse(
			id,
			"ticket-10042",
			"analysis-1",
			action,
			"UNAUTHENTICATED_DEMO",
			"演示管理员",
			"原始回复",
			reviewedReply,
			4,
			"trace-analysis-1",
			Instant.parse("2026-08-25T08:00:00Z")
		);
	}

	private MockMvc mockMvc(AnalysisReviewService service) {
		return MockMvcBuilders
			.standaloneSetup(new AnalysisReviewController(service))
			.setControllerAdvice(new ApiExceptionHandler())
			.build();
	}
}
