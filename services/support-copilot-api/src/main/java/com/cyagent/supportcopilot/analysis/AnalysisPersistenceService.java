package com.cyagent.supportcopilot.analysis;

import java.time.Instant;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

import jakarta.persistence.EntityNotFoundException;

import org.springframework.orm.ObjectOptimisticLockingFailureException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.cyagent.supportcopilot.ticket.TicketRepository;

@Service
public class AnalysisPersistenceService {

	private final TicketRepository ticketRepository;
	private final AnalysisRunRepository analysisRunRepository;
	private final ObjectMapper objectMapper;

	public AnalysisPersistenceService(
		TicketRepository ticketRepository,
		AnalysisRunRepository analysisRunRepository,
		ObjectMapper objectMapper
	) {
		this.ticketRepository = ticketRepository;
		this.analysisRunRepository = analysisRunRepository;
		this.objectMapper = objectMapper;
	}

	@Transactional
	public void persist(String ticketId, long expectedVersion, AnalysisResponse response) {
		// AI 调用不在这个事务中。这里只执行短时间的版本检查和数据库写入。
		var ticket = ticketRepository.findById(ticketId)
			.orElseThrow(() -> new EntityNotFoundException("工单不存在：" + ticketId));
		if (ticket.getVersion() != expectedVersion) {
			throw new TicketVersionConflictException(ticketId, expectedVersion, ticket.getVersion());
		}

		var run = new AnalysisRun();
		run.setId(response.id());
		run.setTicketId(ticketId);
		run.setSourceTicketVersion(expectedVersion);
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

		try {
			// 在方法返回前执行 SQL，确保并发更新也会在本事务中转为明确的版本冲突。
			ticketRepository.flush();
		} catch (ObjectOptimisticLockingFailureException exception) {
			throw new TicketVersionConflictException(ticketId, expectedVersion, null, exception);
		}
	}

	private String serialize(AnalysisResponse response) {
		try {
			return objectMapper.writeValueAsString(response);
		} catch (JacksonException exception) {
			throw new IllegalStateException("Unable to persist analysis response", exception);
		}
	}
}
