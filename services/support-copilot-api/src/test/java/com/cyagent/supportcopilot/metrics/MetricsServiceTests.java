package com.cyagent.supportcopilot.metrics;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
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
		stubEmptyAggregates();
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
		verify(ticketRepository, never()).findAll();
		verify(analysisRunRepository, never()).findAll();
		verify(analysisReviewRepository, never()).findAll();
	}

	@Test
	void exposesOnlyTheMetricsRecordedByTheEvaluationReport() {
		stubEmptyAggregates();
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

	@Test
	void calculatesOperationalRatesFromDatabaseAggregates() {
		var billing = mock(TicketRepository.CategoryCountProjection.class);
		var technical = mock(TicketRepository.CategoryCountProjection.class);
		when(billing.getCategory()).thenReturn("BILLING");
		when(billing.getCount()).thenReturn(4L);
		when(technical.getCategory()).thenReturn("TECHNICAL");
		when(technical.getCount()).thenReturn(2L);
		when(ticketRepository.countByStatusNotIn(List.of("RESOLVED", "CLOSED"))).thenReturn(5L);
		when(ticketRepository.countByPriority("URGENT")).thenReturn(1L);
		when(ticketRepository.countByPriority("HIGH")).thenReturn(2L);
		when(ticketRepository.countByCategory()).thenReturn(List.of(billing, technical));
		when(analysisRunRepository.count()).thenReturn(4L);
		when(analysisRunRepository.countByStatus("SUCCEEDED")).thenReturn(3L);
		when(analysisReviewRepository.count()).thenReturn(4L);
		when(analysisReviewRepository.countByActionIn(List.of(
			com.cyagent.supportcopilot.analysis.review.AnalysisReviewAction.APPROVED,
			com.cyagent.supportcopilot.analysis.review.AnalysisReviewAction.EDITED
		))).thenReturn(3L);
		when(evaluationReportReader.read()).thenReturn(Optional.empty());

		var response = new MetricsService(
			ticketRepository,
			analysisRunRepository,
			analysisReviewRepository,
			evaluationReportReader
		).snapshot();

		assertThat(response.summary().openTickets()).isEqualTo(5L);
		assertThat(response.summary().urgentTickets()).isEqualTo(1L);
		assertThat(response.summary().slaRiskTickets()).isEqualTo(3L);
		assertThat(response.summary().analysisSuccessRate()).isEqualTo(0.75);
		assertThat(response.suggestionAcceptanceRate()).isEqualTo(0.75);
		assertThat(response.categoryDistribution()).extracting(MetricsService.CategoryCount::category)
			.containsExactly("账单支付", "技术问题");
	}

	private void stubEmptyAggregates() {
		when(ticketRepository.countByStatusNotIn(List.of("RESOLVED", "CLOSED"))).thenReturn(0L);
		when(ticketRepository.countByPriority("URGENT")).thenReturn(0L);
		when(ticketRepository.countByPriority("HIGH")).thenReturn(0L);
		when(ticketRepository.countByCategory()).thenReturn(List.of());
		when(analysisRunRepository.count()).thenReturn(0L);
		when(analysisRunRepository.countByStatus("SUCCEEDED")).thenReturn(0L);
		when(analysisReviewRepository.countByActionIn(List.of(
			com.cyagent.supportcopilot.analysis.review.AnalysisReviewAction.APPROVED,
			com.cyagent.supportcopilot.analysis.review.AnalysisReviewAction.EDITED
		))).thenReturn(0L);
		when(analysisReviewRepository.count()).thenReturn(0L);
	}
}
