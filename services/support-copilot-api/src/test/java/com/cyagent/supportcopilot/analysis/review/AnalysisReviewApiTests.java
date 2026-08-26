package com.cyagent.supportcopilot.analysis.review;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
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
import com.cyagent.supportcopilot.ticket.TicketRepository;

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

	@Test
	void recordsRejectionWithRequiredReason() throws Exception {
		var service = mock(AnalysisReviewService.class);
		var response = response("review-rejected", AnalysisReviewAction.REJECTED, null, "证据不足");
		when(service.reject("ticket-10042", "analysis-1", "证据不足")).thenReturn(response);

		mockMvc(service).perform(post("/api/tickets/ticket-10042/analyses/analysis-1/reviews/reject")
				.contentType(APPLICATION_JSON)
				.content("{\"reason\":\"证据不足\"}"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.id").value("review-rejected"))
			.andExpect(jsonPath("$.action").value("REJECTED"))
			.andExpect(jsonPath("$.reviewedReplyContent").value((Object) null))
			.andExpect(jsonPath("$.reason").value("证据不足"));

		verify(service).reject("ticket-10042", "analysis-1", "证据不足");
	}

	@Test
	void rejectsBlankRejectionReasonBeforeCallingTheService() throws Exception {
		var service = mock(AnalysisReviewService.class);

		mockMvc(service).perform(post("/api/tickets/ticket-10042/analyses/analysis-1/reviews/reject")
				.contentType(APPLICATION_JSON)
				.content("{\"reason\":\"   \"}"))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.code").value("INVALID_REQUEST"));

		verify(service, never()).reject(anyString(), anyString(), anyString());
	}

	private AnalysisReviewResponse response(
		String id,
		AnalysisReviewAction action,
		String reviewedReply
	) {
		return response(id, action, reviewedReply, null);
	}

	private AnalysisReviewResponse response(
		String id,
		AnalysisReviewAction action,
		String reviewedReply,
		String reason
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
			reason,
			4,
			"trace-analysis-1",
			Instant.parse("2026-08-25T08:00:00Z")
		);
	}

	private MockMvc mockMvc(AnalysisReviewService service) {
		return MockMvcBuilders
			.standaloneSetup(new AnalysisReviewController(service))
			.setControllerAdvice(new ApiExceptionHandler(mock(TicketRepository.class)))
			.build();
	}
}
