package com.cyagent.supportcopilot.analysis;

import java.util.List;
import java.util.Optional;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

import jakarta.persistence.EntityNotFoundException;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import com.cyagent.supportcopilot.ticket.Ticket;
import com.cyagent.supportcopilot.ticket.TicketRepository;

@Service
public class AnalysisService {

	private static final Logger log = LoggerFactory.getLogger(AnalysisService.class);

	private final TicketRepository ticketRepository;
	private final AnalysisRunRepository analysisRunRepository;
	private final AnalysisPersistenceService analysisPersistenceService;
	private final AiServiceClient aiServiceClient;
	private final MockAnalysisFactory mockAnalysisFactory;
	private final ObjectMapper objectMapper;

	public AnalysisService(
		TicketRepository ticketRepository,
		AnalysisRunRepository analysisRunRepository,
		AnalysisPersistenceService analysisPersistenceService,
		AiServiceClient aiServiceClient,
		MockAnalysisFactory mockAnalysisFactory,
		ObjectMapper objectMapper
	) {
		this.ticketRepository = ticketRepository;
		this.analysisRunRepository = analysisRunRepository;
		this.analysisPersistenceService = analysisPersistenceService;
		this.aiServiceClient = aiServiceClient;
		this.mockAnalysisFactory = mockAnalysisFactory;
		this.objectMapper = objectMapper;
	}

	public AnalysisResponse analyze(String ticketId) {
		var ticket = ticketRepository.findById(ticketId)
			.orElseThrow(() -> new EntityNotFoundException("工单不存在：" + ticketId));
		var sourceTicketVersion = ticket.getVersion();

		// AI 是辅助能力，不是业务事实的来源。
		// 工单已经保存在 Java/H2 中；如果 Python 服务失败，
		// 系统会返回 fallback 分析，而不是让整个流程不可用。
		AnalysisResponse response;
		try {
			response = aiServiceClient.analyze(ticket);
			if (response == null) {
				throw new IllegalStateException("AI service returned an empty response");
			}
		} catch (RuntimeException exception) {
			log.warn("AI service unavailable for ticket {}, using fallback: {}", ticketId, exception.getMessage());
			response = mockAnalysisFactory.create(ticket, "fallback");
		}

		analysisPersistenceService.persist(ticketId, sourceTicketVersion, response);
		return response;
	}

	public void seed(Ticket ticket) {
		if (analysisRunRepository.findFirstByTicketIdOrderByCreatedAtDesc(ticket.getId()).isPresent()) {
			return;
		}
		analysisPersistenceService.persist(
			ticket.getId(),
			ticket.getVersion(),
			mockAnalysisFactory.create(ticket, "mock")
		);
	}

	public Optional<AnalysisResponse> latest(String ticketId) {
		return analysisRunRepository.findFirstByTicketIdOrderByCreatedAtDesc(ticketId).map(this::deserialize);
	}

	public List<AnalysisResponse> history(String ticketId) {
		return analysisRunRepository.findByTicketIdOrderByCreatedAtDesc(ticketId).stream()
			.map(this::deserialize)
			.toList();
	}

	private AnalysisResponse deserialize(AnalysisRun run) {
		try {
			return objectMapper.readValue(run.getResponseJson(), AnalysisResponse.class);
		} catch (JacksonException exception) {
			throw new IllegalStateException("Unable to read analysis response " + run.getId(), exception);
		}
	}
}
