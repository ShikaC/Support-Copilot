package com.cyagent.supportcopilot.analysis;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

import jakarta.persistence.EntityNotFoundException;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.cyagent.supportcopilot.ticket.Ticket;
import com.cyagent.supportcopilot.ticket.TicketRepository;

@Service
public class AnalysisService {

	private static final Logger log = LoggerFactory.getLogger(AnalysisService.class);

	private final TicketRepository ticketRepository;
	private final AnalysisRunRepository analysisRunRepository;
	private final AiServiceClient aiServiceClient;
	private final MockAnalysisFactory mockAnalysisFactory;
	private final ObjectMapper objectMapper;

	public AnalysisService(
		TicketRepository ticketRepository,
		AnalysisRunRepository analysisRunRepository,
		AiServiceClient aiServiceClient,
		MockAnalysisFactory mockAnalysisFactory,
		ObjectMapper objectMapper
	) {
		this.ticketRepository = ticketRepository;
		this.analysisRunRepository = analysisRunRepository;
		this.aiServiceClient = aiServiceClient;
		this.mockAnalysisFactory = mockAnalysisFactory;
		this.objectMapper = objectMapper;
	}

	public AnalysisResponse analyze(String ticketId) {
		var ticket = ticketRepository.findById(ticketId)
			.orElseThrow(() -> new EntityNotFoundException("工单不存在：" + ticketId));

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

		saveRun(ticket, response);
		return response;
	}

	@Transactional
	public void seed(Ticket ticket) {
		if (analysisRunRepository.findFirstByTicketIdOrderByCreatedAtDesc(ticket.getId()).isPresent()) {
			return;
		}
		saveRun(ticket, mockAnalysisFactory.create(ticket, "mock"));
	}

	public Optional<AnalysisResponse> latest(String ticketId) {
		return analysisRunRepository.findFirstByTicketIdOrderByCreatedAtDesc(ticketId).map(this::deserialize);
	}

	public List<AnalysisResponse> history(String ticketId) {
		return analysisRunRepository.findByTicketIdOrderByCreatedAtDesc(ticketId).stream()
			.map(this::deserialize)
			.toList();
	}

	@Transactional
	protected void saveRun(Ticket ticket, AnalysisResponse response) {
		var run = new AnalysisRun();
		run.setId(response.id());
		run.setTicketId(ticket.getId());
		run.setTraceId(response.traceId());
		run.setStatus(response.status());
		run.setMode(response.mode());
		run.setResponseJson(serialize(response));
		run.setCreatedAt(response.createdAt() == null ? Instant.now() : response.createdAt());
		analysisRunRepository.save(run);

		ticket.setCategory(response.classification().category());
		ticket.setPriority(response.classification().priority());
		ticket.setStatus(response.decision().escalationRequired() ? "NEEDS_ESCALATION" : "READY_FOR_REVIEW");
		ticket.setUpdatedAt(Instant.now());
		ticketRepository.save(ticket);
	}

	private String serialize(AnalysisResponse response) {
		try {
			return objectMapper.writeValueAsString(response);
		} catch (JacksonException exception) {
			throw new IllegalStateException("Unable to persist analysis response", exception);
		}
	}

	private AnalysisResponse deserialize(AnalysisRun run) {
		try {
			return objectMapper.readValue(run.getResponseJson(), AnalysisResponse.class);
		} catch (JacksonException exception) {
			throw new IllegalStateException("Unable to read analysis response " + run.getId(), exception);
		}
	}
}
