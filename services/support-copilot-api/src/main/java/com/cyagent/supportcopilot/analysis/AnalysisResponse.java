package com.cyagent.supportcopilot.analysis;

import java.time.Instant;
import java.util.List;

public record AnalysisResponse(
	String id,
	String traceId,
	String status,
	String mode,
	String modelName,
	String promptVersion,
	Classification classification,
	List<WorkflowStep> workflowSteps,
	Retrieval retrieval,
	SuggestedReply suggestedReply,
	Decision decision,
	Usage usage,
	Instant createdAt
) {
	public record Classification(
		String intent,
		String category,
		String priority,
		String sentiment,
		double confidence,
		String reasonSummary
	) {
	}

	public record WorkflowStep(
		String id,
		String name,
		String description,
		String status,
		Long durationMs
	) {
	}

	public record Retrieval(String query, List<RetrievalHit> hits) {
	}

	public record RetrievalHit(
		String chunkId,
		String documentId,
		String documentTitle,
		String section,
		String content,
		String sourceUri,
		String retrievalMethod,
		int initialRank,
		double initialScore,
		int rerankPosition,
		double rerankScore,
		boolean usedAsEvidence
	) {
	}

	public record SuggestedReply(
		String content,
		List<String> citations,
		List<String> warnings
	) {
	}

	public record Decision(boolean escalationRequired, String reason) {
	}

	public record Usage(int inputTokens, int outputTokens, long durationMs) {
	}
}
