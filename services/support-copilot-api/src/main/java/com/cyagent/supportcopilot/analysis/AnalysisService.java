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
import com.cyagent.supportcopilot.common.TraceId;
import com.cyagent.supportcopilot.idempotency.CommandOwnership;

@Service
public class AnalysisService {

	private static final Logger log = LoggerFactory.getLogger(AnalysisService.class);

	private final TicketRepository ticketRepository;
	private final AnalysisRunRepository analysisRunRepository;
	private final AnalysisPersistenceService analysisPersistenceService;
	private final AnalysisSingleFlightCoordinator singleFlightCoordinator;
	private final AiServiceClient aiServiceClient;
	private final MockAnalysisFactory mockAnalysisFactory;
	private final ObjectMapper objectMapper;

	public AnalysisService(
		TicketRepository ticketRepository,
		AnalysisRunRepository analysisRunRepository,
		AnalysisPersistenceService analysisPersistenceService,
		AnalysisSingleFlightCoordinator singleFlightCoordinator,
		AiServiceClient aiServiceClient,
		MockAnalysisFactory mockAnalysisFactory,
		ObjectMapper objectMapper
	) {
		this.ticketRepository = ticketRepository;
		this.analysisRunRepository = analysisRunRepository;
		this.analysisPersistenceService = analysisPersistenceService;
		this.singleFlightCoordinator = singleFlightCoordinator;
		this.aiServiceClient = aiServiceClient;
		this.mockAnalysisFactory = mockAnalysisFactory;
		this.objectMapper = objectMapper;
	}

	public AnalysisResponse analyze(String ticketId) {
		var ticket = ticketRepository.findById(ticketId)
			.orElseThrow(() -> new EntityNotFoundException("工单不存在：" + ticketId));
		var sourceTicketVersion = ticket.getVersion();
		var traceId = TraceId.currentOrCreate();
		var execution = singleFlightCoordinator.execute(
			ticketId,
			sourceTicketVersion,
			AnalysisPolicy.VERSION,
			() -> executeAnalysis(ticket, sourceTicketVersion, traceId)
		);
		if (execution.joined()) {
			log.info(
				"analysis.single_flight_join ticket_id={} source_version={} policy_version={} execution_trace_id={}",
				ticketId,
				sourceTicketVersion,
				AnalysisPolicy.VERSION,
				execution.response().traceId()
			);
		}
		return execution.response();
	}

	public AnalysisResponse analyzeOwned(String ticketId, CommandOwnership ownership) {
		var ticket = ticketRepository.findById(ticketId)
			.orElseThrow(() -> new EntityNotFoundException("工单不存在：" + ticketId));
		var sourceTicketVersion = ticket.getVersion();
		var traceId = TraceId.currentOrCreate();
		return singleFlightCoordinator.execute(
			ownership.idempotencyKey(),
			ticketId,
			sourceTicketVersion,
			AnalysisPolicy.VERSION,
			() -> executeOwnedAnalysis(ticket, sourceTicketVersion, traceId, ownership)
		).response();
	}

	private AnalysisResponse executeAnalysis(Ticket ticket, long sourceTicketVersion, String traceId) {
		var response = requestAnalysis(ticket, traceId);
		analysisPersistenceService.persist(ticket.getId(), sourceTicketVersion, response);
		return response;
	}

	private AnalysisResponse executeOwnedAnalysis(
		Ticket ticket,
		long sourceTicketVersion,
		String traceId,
		CommandOwnership ownership
	) {
		var response = requestAnalysis(ticket, traceId);
		analysisPersistenceService.persistIdempotent(new IdempotentAnalysisPersistence(
			ticket.getId(),
			sourceTicketVersion,
			response,
			ownership
		));
		return response;
	}

	private AnalysisResponse requestAnalysis(Ticket ticket, String traceId) {
		// AI 是辅助能力，不是业务事实的来源。
		// 工单已经保存在 Java/H2 中；如果 Python 服务失败，
		// 系统会返回 fallback 分析，而不是让整个流程不可用。
		AnalysisResponse response;
		try {
			response = aiServiceClient.analyze(ticket, traceId);
		} catch (AiServiceCallException exception) {
			log.atWarn()
				.addKeyValue("trace_id", traceId)
				.addKeyValue("ticket_id", ticket.getId())
				.addKeyValue("reason", exception.getFallbackReason().value())
				.log("analysis.fallback");
			response = mockAnalysisFactory.createFallback(
				ticket,
				traceId,
				exception.getFallbackReason()
			);
		}

		return response;
	}

	public void seed(Ticket ticket) {
		if (analysisRunRepository.findFirstByTicketIdOrderByCreatedAtDesc(ticket.getId()).isPresent()) {
			return;
		}
		analysisPersistenceService.persist(
			ticket.getId(),
			ticket.getVersion(),
			mockAnalysisFactory.createMock(ticket)
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
