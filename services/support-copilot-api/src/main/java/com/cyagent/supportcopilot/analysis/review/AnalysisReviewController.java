package com.cyagent.supportcopilot.analysis.review;

import java.util.List;

import jakarta.validation.Valid;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import com.cyagent.supportcopilot.analysis.review.AnalysisReviewDtos.AnalysisReviewResponse;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewDtos.CreateAnalysisReviewRequest;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewDtos.RejectAnalysisReviewRequest;
import com.cyagent.supportcopilot.idempotency.IdempotencyKey;

@RestController
@RequestMapping("/api/tickets/{ticketId}/analyses/{analysisId}/reviews")
public class AnalysisReviewController {

	private final AnalysisReviewService analysisReviewService;
	private final AnalysisReviewCommandService analysisReviewCommandService;

	public AnalysisReviewController(
		AnalysisReviewService analysisReviewService,
		AnalysisReviewCommandService analysisReviewCommandService
	) {
		this.analysisReviewService = analysisReviewService;
		this.analysisReviewCommandService = analysisReviewCommandService;
	}

	@GetMapping
	List<AnalysisReviewResponse> history(
		@PathVariable String ticketId,
		@PathVariable String analysisId
	) {
		return analysisReviewService.history(ticketId, analysisId);
	}

	@PostMapping
	AnalysisReviewResponse review(
		@PathVariable String ticketId,
		@PathVariable String analysisId,
		@RequestHeader(name = "Idempotency-Key", required = false) String rawIdempotencyKey,
		@Valid @RequestBody CreateAnalysisReviewRequest request
	) {
		return analysisReviewCommandService.review(
			ticketId,
			analysisId,
			request.replyContent(),
			IdempotencyKey.parse(rawIdempotencyKey)
		);
	}

	@PostMapping("/reject")
	AnalysisReviewResponse reject(
		@PathVariable String ticketId,
		@PathVariable String analysisId,
		@RequestHeader(name = "Idempotency-Key", required = false) String rawIdempotencyKey,
		@Valid @RequestBody RejectAnalysisReviewRequest request
	) {
		return analysisReviewCommandService.reject(
			ticketId,
			analysisId,
			request.reason(),
			IdempotencyKey.parse(rawIdempotencyKey)
		);
	}
}
