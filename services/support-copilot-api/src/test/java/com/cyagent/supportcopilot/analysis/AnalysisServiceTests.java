package com.cyagent.supportcopilot.analysis;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.Optional;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

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
	private final AnalysisResponseAccessPolicy accessPolicy = mock(AnalysisResponseAccessPolicy.class);
	private final AnalysisService analysisService = new AnalysisService(
		ticketRepository,
		analysisRunRepository,
		persistenceService,
		new AnalysisSingleFlightCoordinator(),
		aiServiceClient,
		fallbackFactory,
		mock(ObjectMapper.class),
		accessPolicy
	);

	@org.junit.jupiter.api.BeforeEach
	void permitSyntheticUnitResponses() {
		when(accessPolicy.requireReadable(any())).thenAnswer(invocation -> invocation.getArgument(0));
	}

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
	void inaccessibleAiResponseIsRejectedBeforePersistence() {
		var ticket = ticket();
		when(ticketRepository.findById(ticket.getId())).thenReturn(Optional.of(ticket));
		var response = fallbackFactory.createMock(ticket);
		when(aiServiceClient.analyze(eq(ticket), anyString())).thenReturn(response);
		when(accessPolicy.requireReadable(response)).thenThrow(
			new org.springframework.security.access.AccessDeniedException("Restricted evidence"));
		assertThatThrownBy(() -> analysisService.analyze(ticket.getId()))
			.isInstanceOf(org.springframework.security.access.AccessDeniedException.class);
		verify(persistenceService, never()).persist(anyString(), anyLong(), any());
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

	@Test
	void concurrentRequestsForTheSameTicketVersionOnlyAnalyzeAndPersistOnce() throws Exception {
		// Given: one AI execution remains active while a duplicate request arrives.
		var ticket = ticket();
		var aiStarted = new CountDownLatch(1);
		var secondCallerStarted = new CountDownLatch(1);
		var releaseAi = new CountDownLatch(1);
		var response = fallbackFactory.createMock(ticket);
		when(ticketRepository.findById(ticket.getId())).thenReturn(Optional.of(ticket));
		when(aiServiceClient.analyze(eq(ticket), anyString())).thenAnswer(invocation -> {
			aiStarted.countDown();
			if (!releaseAi.await(1, TimeUnit.SECONDS)) {
				throw new IllegalStateException("Timed out waiting to release the AI call");
			}
			return response;
		});

		try (var executor = Executors.newFixedThreadPool(2)) {
			var first = executor.submit(() -> analysisService.analyze(ticket.getId()));
			assertThat(aiStarted.await(1, TimeUnit.SECONDS)).isTrue();
			var second = executor.submit(() -> {
				secondCallerStarted.countDown();
				return analysisService.analyze(ticket.getId());
			});
			assertThat(secondCallerStarted.await(1, TimeUnit.SECONDS)).isTrue();
			assertThatThrownBy(() -> second.get(100, TimeUnit.MILLISECONDS))
				.isInstanceOf(java.util.concurrent.TimeoutException.class);

			// When: the owner completes the shared analysis.
			releaseAi.countDown();

			// Then: both callers receive one result backed by one external call and one write.
			assertThat(first.get(1, TimeUnit.SECONDS)).isSameAs(response);
			assertThat(second.get(1, TimeUnit.SECONDS)).isSameAs(response);
			verify(aiServiceClient, times(1)).analyze(eq(ticket), anyString());
			verify(persistenceService, times(1)).persist(ticket.getId(), ticket.getVersion(), response);
		}
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
