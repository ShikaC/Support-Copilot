package com.cyagent.supportcopilot.analysis.review;

import java.time.Instant;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public final class AnalysisReviewDtos {

	private AnalysisReviewDtos() {
	}

	public record CreateAnalysisReviewRequest(
		@NotBlank @Size(max = 4000) String replyContent
	) {
	}

	public record RejectAnalysisReviewRequest(
		@NotBlank @Size(max = 1000) String reason
	) {
	}

	public record AnalysisReviewResponse(
		String id,
		String ticketId,
		String analysisId,
		AnalysisReviewAction action,
		String reviewerType,
		String reviewerLabel,
		String originalReplyContent,
		String reviewedReplyContent,
		String reason,
		long ticketVersion,
		String traceId,
		Instant createdAt
	) {
	}
}
