package com.cyagent.supportcopilot.ticket;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;

import jakarta.persistence.EntityNotFoundException;

import org.springframework.data.domain.Sort;
import org.springframework.orm.ObjectOptimisticLockingFailureException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.cyagent.supportcopilot.analysis.AnalysisService;
import com.cyagent.supportcopilot.analysis.AnalysisResponse;
import com.cyagent.supportcopilot.analysis.TicketVersionConflictException;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewAction;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewDtos.AnalysisReviewResponse;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewService;
import com.cyagent.supportcopilot.ticket.TicketDtos.CreateTicketRequest;
import com.cyagent.supportcopilot.ticket.TicketDtos.TicketEventResponse;
import com.cyagent.supportcopilot.ticket.TicketDtos.TicketResponse;
import com.cyagent.supportcopilot.ticket.TicketDtos.UpdateTicketRequest;

@Service
public class TicketService {

	private static final AtomicInteger TICKET_SEQUENCE = new AtomicInteger(10100);

	private final TicketRepository ticketRepository;
	private final AnalysisService analysisService;
	private final AnalysisReviewService analysisReviewService;

	public TicketService(
		TicketRepository ticketRepository,
		AnalysisService analysisService,
		AnalysisReviewService analysisReviewService
	) {
		this.ticketRepository = ticketRepository;
		this.analysisService = analysisService;
		this.analysisReviewService = analysisReviewService;
	}

	public List<TicketResponse> list(String status, String priority, String keyword) {
		var normalizedKeyword = keyword == null ? "" : keyword.trim().toLowerCase(Locale.ROOT);
		return ticketRepository.findAll(Sort.by(Sort.Direction.DESC, "createdAt")).stream()
			.filter(ticket -> status == null || status.isBlank() || ticket.getStatus().equals(status))
			.filter(ticket -> priority == null || priority.isBlank() || ticket.getPriority().equals(priority))
			.filter(ticket -> normalizedKeyword.isBlank() || searchable(ticket).contains(normalizedKeyword))
			.map(this::toResponse)
			.toList();
	}

	public TicketResponse get(String id) {
		return toResponse(find(id));
	}

	@Transactional
	public TicketResponse create(CreateTicketRequest request) {
		var now = Instant.now();
		var ticket = new Ticket();
		ticket.setId("ticket-" + UUID.randomUUID());
		ticket.setTicketNo("SC-" + TICKET_SEQUENCE.incrementAndGet());
		ticket.setChannel(request.channel());
		ticket.setCustomerName(request.customerName());
		ticket.setCustomerCompany(request.customerCompany());
		ticket.setCustomerTier(request.customerTier());
		ticket.setSubject(request.subject());
		ticket.setDescription(request.description());
		ticket.setLanguage(request.language() == null || request.language().isBlank() ? "zh-CN" : request.language());
		ticket.setCategory("UNCLASSIFIED");
		ticket.setPriority("MEDIUM");
		ticket.setStatus("NEW");
		ticket.setSlaDeadline(now.plus(Duration.ofHours(8)));
		ticket.setCreatedAt(now);
		ticket.setUpdatedAt(now);
		return toResponse(ticketRepository.save(ticket));
	}

	@Transactional
	public TicketResponse update(String id, UpdateTicketRequest request) {
		var ticket = find(id);
		if (request.status() != null) ticket.setStatus(request.status());
		if (request.priority() != null) ticket.setPriority(request.priority());
		if (request.category() != null) ticket.setCategory(request.category());
		if (request.assigneeName() != null) ticket.setAssigneeName(request.assigneeName());
		ticket.setUpdatedAt(Instant.now());
		return toResponse(ticketRepository.saveAndFlush(ticket));
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
		} catch (ObjectOptimisticLockingFailureException exception) {
			throw new TicketVersionConflictException(id, expectedVersion, null, exception);
		}
		return toResponse(ticket);
	}

	private Ticket find(String id) {
		return ticketRepository.findById(id)
			.orElseThrow(() -> new EntityNotFoundException("工单不存在：" + id));
	}

	private String searchable(Ticket ticket) {
		return String.join(" ",
			ticket.getTicketNo(),
			ticket.getSubject(),
			ticket.getCustomerName(),
			ticket.getCustomerCompany()
		).toLowerCase(Locale.ROOT);
	}

	private TicketResponse toResponse(Ticket ticket) {
		var latest = analysisService.latest(ticket.getId()).orElse(null);
		var latestReview = latest == null ? null : analysisReviewService.latest(latest.id()).orElse(null);
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
				reviewDescription(latestReview.action()),
				latestReview.createdAt()
			));
		}
		return List.copyOf(events);
	}

	private String reviewDescription(AnalysisReviewAction action) {
		return switch (action) {
			case APPROVED -> "未认证演示用户已采纳原始回复建议";
			case EDITED -> "未认证演示用户已编辑并采纳回复建议";
		};
	}
}
