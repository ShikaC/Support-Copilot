package com.cyagent.supportcopilot.metrics;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.util.List;
import java.util.Optional;

import org.junit.jupiter.api.Test;

import com.cyagent.supportcopilot.analysis.AnalysisRunRepository;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewRepository;
import com.cyagent.supportcopilot.ticket.TicketRepository;

class MetricsServiceTests {

	private final TicketRepository ticketRepository = mock(TicketRepository.class);
	private final AnalysisRunRepository analysisRunRepository = mock(AnalysisRunRepository.class);
	private final AnalysisReviewRepository analysisReviewRepository = mock(AnalysisReviewRepository.class);
	private final EvaluationReportReader evaluationReportReader = mock(EvaluationReportReader.class);

	@Test
	void doesNotInventAnalysisQualityMetricsWithoutRecordedRuns() {
		when(ticketRepository.findAll()).thenReturn(List.of());
		when(analysisRunRepository.findAll()).thenReturn(List.of());
		when(analysisReviewRepository.findAll()).thenReturn(List.of());
		when(evaluationReportReader.read()).thenReturn(Optional.empty());

		var response = new MetricsService(
			ticketRepository,
			analysisRunRepository,
			analysisReviewRepository,
			evaluationReportReader
		).snapshot();

		assertThat(response.summary().analysisSuccessRate()).isNull();
		assertThat(response.ticketTrend()).isEmpty();
		assertThat(response.analysisLatency()).isNull();
		assertThat(response.suggestionAcceptanceRate()).isNull();
		assertThat(response.evaluation()).isNull();
	}

	@Test
	void exposesOnlyTheMetricsRecordedByTheEvaluationReport() {
		when(ticketRepository.findAll()).thenReturn(List.of());
		when(analysisRunRepository.findAll()).thenReturn(List.of());
		when(analysisReviewRepository.findAll()).thenReturn(List.of());
		when(evaluationReportReader.read()).thenReturn(Optional.of(
			new EvaluationReportReader.EvaluationSnapshot(
				"tickets.jsonl",
				"mock",
				"deterministic-demo",
				"ticket-analysis-v1",
				31,
				10,
				3,
				1.0,
				1.0,
				1.0,
				1.0,
				0.161,
				1,
				0,
				true,
				java.time.Instant.parse("2026-08-26T06:53:34.585167Z")
			)
		));

		var response = new MetricsService(
			ticketRepository,
			analysisRunRepository,
			analysisReviewRepository,
			evaluationReportReader
		).snapshot();

		assertThat(response.evaluation()).isNotNull();
		assertThat(response.evaluation().datasetName()).isEqualTo("tickets.jsonl");
		assertThat(response.evaluation().totalCases()).isEqualTo(31);
		assertThat(response.evaluation().hitRateAtK()).isEqualTo(1.0);
		assertThat(response.evaluation().citationCoverage()).isEqualTo(1.0);
		assertThat(response.evaluation().p95DurationMs()).isEqualTo(1);
		assertThat(response.evaluation().thresholdFailureCount()).isZero();
		assertThat(response.evaluation().passed()).isTrue();
	}
}
