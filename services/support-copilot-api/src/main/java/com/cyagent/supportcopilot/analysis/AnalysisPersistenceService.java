package com.cyagent.supportcopilot.analysis;

import java.time.Instant;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

import jakarta.persistence.EntityNotFoundException;

import org.springframework.orm.ObjectOptimisticLockingFailureException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.cyagent.supportcopilot.ticket.TicketRepository;
import com.cyagent.supportcopilot.ticket.TicketDomain;
import com.cyagent.supportcopilot.audit.AuditAction;
import com.cyagent.supportcopilot.audit.AuditEventCommand;
import com.cyagent.supportcopilot.audit.AuditEventRecorder;
import com.cyagent.supportcopilot.audit.AuditMetadata;
import com.cyagent.supportcopilot.audit.AuditTargetType;

@Service
public class AnalysisPersistenceService {

	private final TicketRepository ticketRepository;
	private final AnalysisRunRepository analysisRunRepository;
	private final ObjectMapper objectMapper;
	private final AuditEventRecorder auditEventRecorder;

	public AnalysisPersistenceService(
		TicketRepository ticketRepository,
		AnalysisRunRepository analysisRunRepository,
		ObjectMapper objectMapper,
		AuditEventRecorder auditEventRecorder
	) {
		this.ticketRepository = ticketRepository;
		this.analysisRunRepository = analysisRunRepository;
		this.objectMapper = objectMapper;
		this.auditEventRecorder = auditEventRecorder;
	}

	@Transactional
	public void persist(String ticketId, long expectedVersion, AnalysisResponse response) {
		// AI 调用不在这个事务中。这里只执行短时间的版本检查和数据库写入。
		var ticket = ticketRepository.findById(ticketId)
			.orElseThrow(() -> new EntityNotFoundException("工单不存在：" + ticketId));
		if (ticket.getVersion() != expectedVersion) {
			throw new TicketVersionConflictException(ticketId, expectedVersion, ticket.getVersion());
		}
		var category = TicketDomain.parseCategory(response.classification().category());
		var priority = TicketDomain.parsePriority(response.classification().priority());
		TicketDomain.parseAnalysisStatus(response.status());
		var resultStatus = TicketDomain.analysisResultStatus(
			ticketId,
			ticket.getStatus(),
			response.decision().escalationRequired()
		);

		var run = new AnalysisRun();
		run.setId(response.id());
		run.setTicketId(ticketId);
		run.setSourceTicketVersion(expectedVersion);
		run.setTraceId(response.traceId());
		run.setStatus(response.status());
		run.setMode(response.mode());
		run.setFallbackReason(response.fallbackReason());
		run.setResponseJson(serialize(response));
		run.setCreatedAt(response.createdAt() == null ? Instant.now() : response.createdAt());
		analysisRunRepository.save(run);

		ticket.setCategory(category.name());
		ticket.setPriority(priority.name());
		ticket.setStatus(resultStatus.name());
		ticket.setUpdatedAt(Instant.now());
		ticketRepository.save(ticket);

		try {
			// 在方法返回前执行 SQL，确保并发更新也会在本事务中转为明确的版本冲突。
			ticketRepository.flush();
		} catch (ObjectOptimisticLockingFailureException exception) {
			throw new TicketVersionConflictException(ticketId, expectedVersion, null, exception);
		}
		auditEventRecorder.record(new AuditEventCommand(
			AuditAction.ANALYSIS_PERSISTED,
			AuditTargetType.ANALYSIS,
			response.id(),
			expectedVersion,
			new AuditMetadata.Analysis(
				AuditMetadata.AnalysisMode.parse(response.mode()),
				AuditMetadata.AnalysisStatus.parse(response.status()),
				response.fallbackReason(),
				expectedVersion,
				response.id()
			)
		));
	}

	private String serialize(AnalysisResponse response) {
		try {
			return objectMapper.writeValueAsString(response);
		} catch (JacksonException exception) {
			throw new IllegalStateException("Unable to persist analysis response", exception);
		}
	}
}
