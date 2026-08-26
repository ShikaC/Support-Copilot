package com.cyagent.supportcopilot.analysis.review;

import com.cyagent.supportcopilot.idempotency.CommandOwnership;

public record IdempotentAnalysisReview(
	String ticketId,
	String analysisId,
	String content,
	CommandOwnership ownership
) {
}
