package com.cyagent.supportcopilot.quality;

import java.util.List;

public record QualityReport(
	int schemaVersion, String id, Kind kind, String title, String dataset, String generatedAt,
	List<SourceFile> sourceFiles, int sampleCount, int distinctCaseCount, int humanReviewedCount,
	Double answerAccuracy, Double businessResolutionRate, Double timeSavedMinutes, Double cost,
	Outcomes outcomes, List<Metric> metrics, List<Group> groups, List<Failure> failures,
	List<String> gateReasons, List<String> limitations
) {
	public enum Kind { LIVE_EVALUATION, BUSINESS_BENCHMARK }
	public enum Unit { RATE, MS, NUMBER }
	public enum FailureOutcome { EVIDENCE_INSUFFICIENT, TIMEOUT, OTHER_FALLBACK, ERROR }
	public record SourceFile(String name, String sha256) {}
	public record Outcomes(int normalLive, int evidenceInsufficient, int timeout, int otherFallback, int error) {
		long total() { return (long) normalLive + evidenceInsufficient + timeout + otherFallback + error; }
	}
	public record Metric(String id, String label, Double value, Unit unit, Integer denominator, String description) {}
	public record Group(int concurrency, int total, int normalLive, int evidenceInsufficient, int timeout,
		int otherFallback, int error, double p50Ms, double p95Ms, int apiCompleted, int persisted) {}
	public record Failure(String caseId, Integer concurrency, FailureOutcome outcome, String reason, String traceId) {}
}
