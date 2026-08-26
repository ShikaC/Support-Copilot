package com.cyagent.supportcopilot.metrics;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

import java.nio.file.Files;
import java.nio.file.Path;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import tools.jackson.databind.ObjectMapper;

class EvaluationReportReaderTests {

	private final ObjectMapper objectMapper = new ObjectMapper();

	@Test
	void readsTheStableFieldsUsedByTheQualityPage(@TempDir Path tempDir) throws Exception {
		var reportPath = tempDir.resolve("mock-latest.json");
		Files.writeString(reportPath, """
			{
			  "generated_at": "2026-08-26T06:53:34.585167Z",
			  "dataset_name": "tickets.jsonl",
			  "mode": "mock",
			  "model_names": ["deterministic-demo"],
			  "prompt_versions": ["ticket-analysis-v1"],
			  "top_n": 10,
			  "top_k": 3,
			  "metrics": {
			    "total_cases": 31,
			    "hit_rate_at_k": 1.0,
			    "mrr": 1.0,
			    "citation_coverage": 1.0,
			    "no_evidence_safety_rate": 1.0,
			    "average_duration_ms": 0.16129032258064516,
			    "p95_duration_ms": 1
			  },
			  "threshold_failures": [],
			  "passed": true
			}
			""");

		var report = new EvaluationReportReader(objectMapper, reportPath).read().orElseThrow();

		assertThat(report.datasetName()).isEqualTo("tickets.jsonl");
		assertThat(report.modelName()).isEqualTo("deterministic-demo");
		assertThat(report.totalCases()).isEqualTo(31);
		assertThat(report.hitRateAtK()).isEqualTo(1.0);
		assertThat(report.averageDurationMs()).isCloseTo(0.161, within(0.001));
		assertThat(report.p95DurationMs()).isEqualTo(1);
		assertThat(report.thresholdFailureCount()).isZero();
		assertThat(report.passed()).isTrue();
	}

	@Test
	void treatsMissingReportsAsUnavailable(@TempDir Path tempDir) {
		var report = new EvaluationReportReader(
			objectMapper,
			tempDir.resolve("missing.json")
		).read();

		assertThat(report).isEmpty();
	}

	@Test
	void treatsMalformedReportsAsUnavailable(@TempDir Path tempDir) throws Exception {
		var reportPath = tempDir.resolve("broken.json");
		Files.writeString(reportPath, "{\"metrics\": {\"total_cases\": \"thirty-one\"}}");

		var report = new EvaluationReportReader(objectMapper, reportPath).read();

		assertThat(report).isEmpty();
	}

	@Test
	void treatsOutOfRangeMetricsAsUnavailable(@TempDir Path tempDir) throws Exception {
		var reportPath = tempDir.resolve("invalid-metrics.json");
		Files.writeString(reportPath, """
			{
			  "generated_at": "2026-08-26T06:53:34.585167Z",
			  "dataset_name": "tickets.jsonl",
			  "mode": "mock",
			  "model_names": ["deterministic-demo"],
			  "prompt_versions": ["ticket-analysis-v1"],
			  "top_n": 10,
			  "top_k": 3,
			  "metrics": {
			    "total_cases": 31,
			    "hit_rate_at_k": 1.1,
			    "mrr": 1.0,
			    "citation_coverage": 1.0,
			    "no_evidence_safety_rate": 1.0,
			    "average_duration_ms": 0.161,
			    "p95_duration_ms": 1
			  },
			  "threshold_failures": [],
			  "passed": true
			}
			""");

		var report = new EvaluationReportReader(objectMapper, reportPath).read();

		assertThat(report).isEmpty();
	}

	@Test
	void readsLiveEvaluationSummaryWithoutTreatingItAsProductionAccuracy(@TempDir Path tempDir) throws Exception {
		var reportPath = tempDir.resolve("live-latest.json");
		Files.writeString(reportPath, """
			{
			  "report_kind": "live-evaluation",
			  "run": {
			    "timestamp": "2026-08-27T00:00:00Z",
			    "dataset_id": "support-copilot-live-synthetic",
			    "dataset_version": "1.0.0",
			    "prompt_version": "ticket-analysis-v1",
			    "top_n": 10,
			    "top_k": 3
			  },
			  "provenance": {"chat_model": "chat-model"},
			  "summary": {
			    "total_cases": 4,
			    "retrieval_success_rate": 1.0,
			    "mean_reciprocal_rank": 1.0,
			    "citation_valid_rate": 1.0,
			    "no_evidence_safety_rate": 1.0,
			    "average_latency_ms": 42.5,
			    "p95_latency_ms": 50,
			    "gate_reasons": ["human-review-incomplete"],
			    "publishable": false
			  }
			}
			""");

		var report = new EvaluationReportReader(objectMapper, reportPath).read().orElseThrow();

		assertThat(report.datasetName()).isEqualTo("support-copilot-live-synthetic@1.0.0");
		assertThat(report.mode()).isEqualTo("live");
		assertThat(report.totalCases()).isEqualTo(4);
		assertThat(report.thresholdFailureCount()).isEqualTo(1);
		assertThat(report.passed()).isFalse();
	}
}
