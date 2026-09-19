package com.cyagent.supportcopilot.analysis.review;

import org.springframework.stereotype.Service;

import com.cyagent.supportcopilot.analysis.review.AnalysisReviewDtos.AnalysisReviewResponse;
import com.cyagent.supportcopilot.idempotency.CommandIdempotencyCoordinator;
import com.cyagent.supportcopilot.idempotency.CommandRequestFactory;
import com.cyagent.supportcopilot.idempotency.IdempotencyKey;

@Service
public class AnalysisReviewCommandService {

	private final AnalysisReviewService reviewService;
	private final CommandIdempotencyCoordinator idempotencyCoordinator;
	private final CommandRequestFactory commandRequestFactory;

	public AnalysisReviewCommandService(
		AnalysisReviewService reviewService,
		CommandIdempotencyCoordinator idempotencyCoordinator,
		CommandRequestFactory commandRequestFactory
	) {
		this.reviewService = reviewService;
		this.idempotencyCoordinator = idempotencyCoordinator;
		this.commandRequestFactory = commandRequestFactory;
	}

	public AnalysisReviewResponse review(
		String ticketId,
		String analysisId,
		String replyContent,
		IdempotencyKey key
	) {
		reviewService.requireReadable(ticketId, analysisId);
		var request = commandRequestFactory.review(key, ticketId, analysisId, replyContent);
		var response = idempotencyCoordinator.execute(
			request,
			AnalysisReviewResponse.class,
			ownership -> reviewService.reviewIdempotent(
				new IdempotentAnalysisReview(ticketId, analysisId, replyContent, ownership)
			)
		);
		reviewService.requireReadable(ticketId, analysisId);
		return response;
	}

	public AnalysisReviewResponse reject(
		String ticketId,
		String analysisId,
		String reason,
		IdempotencyKey key
	) {
		reviewService.requireReadable(ticketId, analysisId);
		var request = commandRequestFactory.reject(key, ticketId, analysisId, reason);
		var response = idempotencyCoordinator.execute(
			request,
			AnalysisReviewResponse.class,
			ownership -> reviewService.rejectIdempotent(
				new IdempotentAnalysisReview(ticketId, analysisId, reason, ownership)
			)
		);
		reviewService.requireReadable(ticketId, analysisId);
		return response;
	}
}
