package com.cyagent.supportcopilot.analysis.review;

import java.util.List;

import jakarta.validation.Valid;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.cyagent.supportcopilot.analysis.review.AnalysisReviewDtos.AnalysisReviewResponse;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewDtos.CreateAnalysisReviewRequest;

@RestController
@RequestMapping("/api/tickets/{ticketId}/analyses/{analysisId}/reviews")
public class AnalysisReviewController {

	private final AnalysisReviewService analysisReviewService;

	public AnalysisReviewController(AnalysisReviewService analysisReviewService) {
		this.analysisReviewService = analysisReviewService;
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
		@Valid @RequestBody CreateAnalysisReviewRequest request
	) {
		return analysisReviewService.review(ticketId, analysisId, request.replyContent());
	}
}
