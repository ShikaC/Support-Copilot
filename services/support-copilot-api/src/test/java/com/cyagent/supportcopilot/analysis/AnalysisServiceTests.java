package com.cyagent.supportcopilot.analysis;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.Optional;

import tools.jackson.databind.ObjectMapper;

import org.junit.jupiter.api.Test;

import com.cyagent.supportcopilot.ticket.Ticket;
import com.cyagent.supportcopilot.ticket.TicketRepository;

class AnalysisServiceTests {

	private final TicketRepository ticketRepository = mock(TicketRepository.class);
	private final AnalysisRunRepository analysisRunRepository = mock(AnalysisRunRepository.class);
	private final AnalysisPersistenceService persistenceService = mock(AnalysisPersistenceService.class);
	private final AiServiceClient aiServiceClient = mock(AiServiceClient.class);
	private final MockAnalysisFactory fallbackFactory = new MockAnalysisFactory();
	private final AnalysisService analysisService = new AnalysisService(
		ticketRepository,
		analysisRunRepository,
		persistenceService,
		aiServiceClient,
		fallbackFactory,
		mock(ObjectMapper.class)
	);

	@Test
	void namedAiServiceFailureIsPersistedAsFallback() {
		// Given: the typed AI boundary reports that Python is unavailable.
		var ticket = ticket();
		when(ticketRepository.findById(ticket.getId())).thenReturn(Optional.of(ticket));
		when(aiServiceClient.analyze(eq(ticket), anyString())).thenThrow(
			new AiServiceCallException(FallbackReason.AI_SERVICE_UNAVAILABLE)
		);

		// When: Java protects the business flow with a local analysis result.
		var response = analysisService.analyze(ticket.getId());

		// Then: the named reason survives into the result passed to persistence.
		assertThat(response.fallbackReason()).isEqualTo(FallbackReason.AI_SERVICE_UNAVAILABLE);
		verify(persistenceService).persist(ticket.getId(), ticket.getVersion(), response);
	}

	@Test
	void programmingFailureIsNotHiddenAsFallback() {
		// Given: an unexpected programming defect escapes the AI client boundary.
		var ticket = ticket();
		when(ticketRepository.findById(ticket.getId())).thenReturn(Optional.of(ticket));
		when(aiServiceClient.analyze(eq(ticket), anyString())).thenThrow(
			new IllegalStateException("simulated programming defect")
		);

		// When/Then: AnalysisService propagates the defect without persisting fake fallback.
		assertThatThrownBy(() -> analysisService.analyze(ticket.getId()))
			.isInstanceOf(IllegalStateException.class)
			.hasMessage("simulated programming defect");
		verify(persistenceService, never()).persist(
			anyString(),
			anyLong(),
			any(AnalysisResponse.class)
		);
	}

	private Ticket ticket() {
		var ticket = new Ticket();
		ticket.setId("ticket-analysis-service");
		ticket.setTicketNo("SC-ANALYSIS-SERVICE");
		ticket.setSubject("企业账号无法登录");
		ticket.setDescription("管理员和成员都无法进入工作区。");
		ticket.setLanguage("zh-CN");
		ticket.setCustomerTier("ENTERPRISE");
		ticket.setCategory("ACCOUNT_ACCESS");
		ticket.setPriority("HIGH");
		ticket.setCreatedAt(Instant.now());
		return ticket;
	}
}
