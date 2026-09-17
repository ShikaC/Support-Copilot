package com.cyagent.supportcopilot.ticket;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;

import com.cyagent.supportcopilot.analysis.AnalysisResponse;
import com.cyagent.supportcopilot.analysis.AnalysisService;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewService;
import com.cyagent.supportcopilot.audit.AuditEventRecorder;

class TicketServiceListTests {

	private final TicketRepository ticketRepository = mock(TicketRepository.class);
	private final AnalysisService analysisService = mock(AnalysisService.class);
	private final AnalysisReviewService analysisReviewService = mock(AnalysisReviewService.class);

	@Test
	void loadsListAnalysisAndReviewDataInBatches() {
		var ticket = ticket("ticket-1", "2026-07-28T07:31:00Z");
		var analysis = new AnalysisResponse(
			"analysis-1",
			null,
			"SUCCEEDED",
			"mock",
			null,
			null,
			null,
			null,
			null,
			null,
			null,
			new AnalysisResponse.Decision(false, "无需升级"),
			null,
			Instant.parse("2026-07-28T07:32:00Z")
		);
		when(ticketRepository.findQueuePage(any(TicketQueueQuery.class), eq(null), eq(21))).thenReturn(List.of(ticket));
		when(analysisService.latestForTickets(List.of("ticket-1"))).thenReturn(Map.of("ticket-1", analysis));
		when(analysisReviewService.latestForAnalyses(List.of("analysis-1"))).thenReturn(Map.of());

		var response = new TicketService(
			ticketRepository,
			analysisService,
			analysisReviewService,
			mock(AuditEventRecorder.class)
		).list(null, null, null, null, null, 20);

		assertThat(response.items()).hasSize(1);
		assertThat(response.items().getFirst().latestAnalysis()).isEqualTo(analysis);
		verify(analysisService).latestForTickets(List.of("ticket-1"));
		verify(analysisReviewService).latestForAnalyses(List.of("analysis-1"));
		verify(analysisService, never()).latest("ticket-1");
		verify(analysisReviewService, never()).latest("analysis-1");
	}

	private Ticket ticket(String id, String createdAt) {
		var ticket = new Ticket();
		ticket.setId(id);
		ticket.setCreatedAt(Instant.parse(createdAt));
		ticket.setUpdatedAt(Instant.parse(createdAt));
		return ticket;
	}
}
