package com.cyagent.supportcopilot.ticket;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

import jakarta.persistence.EntityNotFoundException;

import org.springframework.orm.ObjectOptimisticLockingFailureException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.cyagent.supportcopilot.analysis.AnalysisService;
import com.cyagent.supportcopilot.analysis.AnalysisResponse;
import com.cyagent.supportcopilot.analysis.TicketVersionConflictException;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewDtos.AnalysisReviewResponse;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewService;
import com.cyagent.supportcopilot.audit.AuditAction;
import com.cyagent.supportcopilot.audit.AuditChangedField;
import com.cyagent.supportcopilot.audit.AuditEventCommand;
import com.cyagent.supportcopilot.audit.AuditEventRecorder;
import com.cyagent.supportcopilot.audit.AuditMetadata;
import com.cyagent.supportcopilot.audit.AuditTargetType;
import com.cyagent.supportcopilot.ticket.TicketDtos.CreateTicketRequest;
import com.cyagent.supportcopilot.ticket.TicketDtos.TicketEventResponse;
import com.cyagent.supportcopilot.ticket.TicketDtos.TicketResponse;
import com.cyagent.supportcopilot.ticket.TicketDtos.UpdateTicketRequest;

@Service
public class TicketService {

	private static final int DEFAULT_PAGE_SIZE = 20;
	private static final int MAX_PAGE_SIZE = 100;

	private final TicketRepository ticketRepository;
	private final AnalysisService analysisService;
	private final AnalysisReviewService analysisReviewService;
	private final AuditEventRecorder auditEventRecorder;

	public TicketService(
		TicketRepository ticketRepository,
		AnalysisService analysisService,
		AnalysisReviewService analysisReviewService,
		AuditEventRecorder auditEventRecorder
	) {
		this.ticketRepository = ticketRepository;
		this.analysisService = analysisService;
		this.analysisReviewService = analysisReviewService;
		this.auditEventRecorder = auditEventRecorder;
	}

	@Transactional(readOnly = true)
	public TicketPage list(String status, String priority, String category, String keyword, String cursor, Integer requestedLimit) {
		return list(TicketQueueQuery.parse(status, priority, category, keyword, null, null), cursor, requestedLimit);
	}

	@Transactional(readOnly = true)
	public TicketPage list(TicketQueueQuery query, String cursor, Integer requestedLimit) {
		var pageSize = pageSize(requestedLimit);
		var decodedCursor = cursor == null || cursor.isBlank() ? null : TicketQueueCursor.decode(cursor, query);
		var tickets = ticketRepository.findQueuePage(query, decodedCursor, pageSize + 1);
		var hasMore = tickets.size() > pageSize;
		var pageTickets = hasMore ? tickets.subList(0, pageSize) : tickets;
		var nextCursor = hasMore ? TicketQueueCursor.from(pageTickets.getLast()).encode(query) : null;
		return new TicketPage(toResponses(pageTickets), nextCursor, pageSize, ticketRepository.countQueue(query));
	}

	public TicketResponse get(String id) {
		return toResponse(find(id));
	}

	@Transactional
	public TicketResponse create(CreateTicketRequest request) {
		var now = Instant.now();
		var ticket = new Ticket();
		ticket.setId("ticket-" + UUID.randomUUID());
		ticket.setTicketNo(newTicketNumber());
		ticket.setChannel(request.channel().name());
		ticket.setCustomerName(request.customerName());
		ticket.setCustomerCompany(request.customerCompany());
		ticket.setCustomerTier(request.customerTier().name());
		ticket.setSubject(request.subject());
		ticket.setDescription(request.description());
		ticket.setLanguage(request.language() == null || request.language().isBlank() ? "zh-CN" : request.language());
		ticket.setCategory("UNCLASSIFIED");
		ticket.setPriority("MEDIUM");
		ticket.setStatus("NEW");
		ticket.setSlaDeadline(now.plus(Duration.ofHours(8)));
		ticket.setCreatedAt(now);
		ticket.setUpdatedAt(now);
		var saved = ticketRepository.saveAndFlush(ticket);
		auditEventRecorder.record(new AuditEventCommand(
			AuditAction.TICKET_CREATED,
			AuditTargetType.TICKET,
			saved.getId(),
			saved.getVersion(),
			new AuditMetadata.None()
		));
		return toResponse(saved);
	}

	@Transactional
	public TicketResponse update(String id, UpdateTicketRequest request) {
		var ticket = find(id);
		if (ticket.getVersion() != request.expectedVersion()) {
			throw new TicketVersionConflictException(id, request.expectedVersion(), ticket.getVersion());
		}
		var changedFields = new ArrayList<AuditChangedField>();
		if (request.status() != null) {
			TicketDomain.requireManualTransition(id, ticket.getStatus(), request.status());
			if (!ticket.getStatus().equals(request.status().name())) {
				ticket.setStatus(request.status().name());
				if (request.status() == TicketDomain.Status.RESOLVED) ticket.setResolvedAt(Instant.now());
				changedFields.add(AuditChangedField.STATUS);
			}
		}
		if (request.priority() != null && !request.priority().name().equals(ticket.getPriority())) {
			ticket.setPriority(request.priority().name());
			changedFields.add(AuditChangedField.PRIORITY);
		}
		if (request.category() != null && !request.category().name().equals(ticket.getCategory())) {
			ticket.setCategory(request.category().name());
			changedFields.add(AuditChangedField.CATEGORY);
		}
		if (request.assigneeName() != null && !request.assigneeName().equals(ticket.getAssigneeName())) {
			ticket.setAssigneeName(request.assigneeName());
			changedFields.add(AuditChangedField.ASSIGNEE);
		}
		if (changedFields.isEmpty()) {
			return toResponse(ticket);
		}
		ticket.setUpdatedAt(Instant.now());
		try {
			var saved = ticketRepository.saveAndFlush(ticket);
			auditEventRecorder.record(new AuditEventCommand(
				AuditAction.TICKET_UPDATED,
				AuditTargetType.TICKET,
				saved.getId(),
				saved.getVersion(),
				new AuditMetadata.TicketChange(changedFields)
			));
			return toResponse(saved);
		} catch (ObjectOptimisticLockingFailureException exception) {
			throw new TicketVersionConflictException(id, request.expectedVersion(), null, exception);
		}
	}

	@Transactional
	public TicketResponse unassign(String id, long expectedVersion) {
		var ticket = find(id);
		if (ticket.getVersion() != expectedVersion) {
			throw new TicketVersionConflictException(id, expectedVersion, ticket.getVersion());
		}
		if (ticket.getAssigneeName() == null) {
			// 重复点击不会再次修改数据库，因此同一个请求可以安全重试。
			return toResponse(ticket);
		}
		if ("RESOLVED".equals(ticket.getStatus()) || "CLOSED".equals(ticket.getStatus())) {
			throw new TicketStateConflictException(id, ticket.getStatus());
		}

		ticket.setAssigneeName(null);
		ticket.setUpdatedAt(Instant.now());
		try {
			// 显式 flush，让并发更新在本次请求中尽早转换成可识别的版本冲突。
			ticketRepository.saveAndFlush(ticket);
			auditEventRecorder.record(new AuditEventCommand(
				AuditAction.TICKET_UNASSIGNED,
				AuditTargetType.TICKET,
				ticket.getId(),
				ticket.getVersion(),
				new AuditMetadata.TicketChange(List.of(AuditChangedField.ASSIGNEE))
			));
		} catch (ObjectOptimisticLockingFailureException exception) {
			throw new TicketVersionConflictException(id, expectedVersion, null, exception);
		}
		return toResponse(ticket);
	}

	private Ticket find(String id) {
		return ticketRepository.findById(id)
			.orElseThrow(() -> new EntityNotFoundException("工单不存在：" + id));
	}

	private int pageSize(Integer requestedLimit) {
		var size = requestedLimit == null ? DEFAULT_PAGE_SIZE : requestedLimit;
		if (size < 1 || size > MAX_PAGE_SIZE) {
			throw TicketQueryException.invalidPageSize();
		}
		return size;
	}

	private String newTicketNumber() {
		return "SC-" + UUID.randomUUID().toString().replace("-", "").substring(0, 29).toUpperCase(Locale.ROOT);
	}

	private List<TicketResponse> toResponses(List<Ticket> tickets) {
		var latestByTicket = analysisService.latestForTickets(
			tickets.stream().map(Ticket::getId).toList()
		);
		var latestAnalyses = latestByTicket.values().stream().map(AnalysisResponse::id).toList();
		var latestReviews = analysisReviewService.latestForAnalyses(latestAnalyses);
		return tickets.stream()
			.map(ticket -> {
				var latest = latestByTicket.get(ticket.getId());
				var latestReview = latest == null ? null : latestReviews.get(latest.id());
				return toResponse(ticket, latest, latestReview);
			})
			.toList();
	}

	private TicketResponse toResponse(Ticket ticket) {
		var latest = analysisService.latest(ticket.getId()).orElse(null);
		var latestReview = latest == null ? null : analysisReviewService.latest(latest.id()).orElse(null);
		return toResponse(ticket, latest, latestReview);
	}

	private TicketResponse toResponse(
		Ticket ticket,
		AnalysisResponse latest,
		AnalysisReviewResponse latestReview
	) {
		var events = events(ticket, latest, latestReview);

		return new TicketResponse(
			ticket.getId(),
			ticket.getTicketNo(),
			ticket.getChannel(),
			ticket.getCustomerName(),
			ticket.getCustomerCompany(),
			ticket.getCustomerTier(),
			ticket.getSubject(),
			ticket.getDescription(),
			ticket.getLanguage(),
			ticket.getCategory(),
			ticket.getPriority(),
			ticket.getStatus(),
			ticket.getAssigneeName(),
			ticket.getSlaDeadline(),
			ticket.getCreatedAt(),
			ticket.getUpdatedAt(),
			ticket.getVersion(),
			latest,
			latestReview,
			events
		);
	}

	private List<TicketEventResponse> events(
		Ticket ticket,
		AnalysisResponse latest,
		AnalysisReviewResponse latestReview
	) {
		var events = new ArrayList<TicketEventResponse>();
		events.add(new TicketEventResponse(
			"created-" + ticket.getId(),
			"工单创建",
			"已进入待处理队列",
			ticket.getCreatedAt()
		));

		if (latest != null) {
			events.add(new TicketEventResponse(
				"analysis-" + latest.id(),
				"辅助分析完成",
				latest.decision().reason(),
				latest.createdAt()
			));
		}
		if (latestReview != null) {
			events.add(new TicketEventResponse(
				latestReview.id(),
				"人工审核已记录",
				reviewDescription(latestReview),
				latestReview.createdAt()
			));
		}
		return List.copyOf(events);
	}

	private String reviewDescription(AnalysisReviewResponse review) {
		return switch (review.action()) {
			case APPROVED -> review.reviewerLabel() + "已采纳原始回复建议";
			case EDITED -> review.reviewerLabel() + "已编辑并采纳回复建议";
			case REJECTED -> review.reviewerLabel() + "已拒绝回复建议：" + review.reason();
		};
	}

	public record TicketPage(List<TicketResponse> items, String nextCursor, int limit, long totalCount) {
		public TicketPage(List<TicketResponse> items, String nextCursor, int limit) {
			this(items, nextCursor, limit, items.size());
		}
		public TicketPage {
			items = List.copyOf(items);
		}
	}
}
