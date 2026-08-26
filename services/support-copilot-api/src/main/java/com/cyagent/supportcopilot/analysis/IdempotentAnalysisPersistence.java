package com.cyagent.supportcopilot.analysis;

import com.cyagent.supportcopilot.idempotency.CommandOwnership;

public record IdempotentAnalysisPersistence(
	String ticketId,
	long expectedVersion,
	AnalysisResponse response,
	CommandOwnership ownership
) {
}
