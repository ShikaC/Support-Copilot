package com.cyagent.supportcopilot.metrics;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.util.List;

import org.junit.jupiter.api.Test;

import com.cyagent.supportcopilot.analysis.AnalysisRunRepository;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewRepository;
import com.cyagent.supportcopilot.ticket.TicketRepository;

class MetricsServiceTests {

	private final TicketRepository ticketRepository = mock(TicketRepository.class);
	private final AnalysisRunRepository analysisRunRepository = mock(AnalysisRunRepository.class);
	private final AnalysisReviewRepository analysisReviewRepository = mock(AnalysisReviewRepository.class);

	@Test
	void doesNotInventAnalysisQualityMetricsWithoutRecordedRuns() {
		when(ticketRepository.findAll()).thenReturn(List.of());
		when(analysisRunRepository.findAll()).thenReturn(List.of());
		when(analysisReviewRepository.findAll()).thenReturn(List.of());

		var response = new MetricsService(
			ticketRepository,
			analysisRunRepository,
			analysisReviewRepository
		).snapshot();

		assertThat(response.summary().analysisSuccessRate()).isNull();
		assertThat(response.ticketTrend()).isEmpty();
		assertThat(response.analysisLatency()).isNull();
		assertThat(response.suggestionAcceptanceRate()).isNull();
		assertThat(response.evaluation()).isNull();
	}
}
