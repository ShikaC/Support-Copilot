package com.cyagent.supportcopilot.ticket;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;

import jakarta.persistence.EntityNotFoundException;

import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.cyagent.supportcopilot.analysis.AnalysisService;
import com.cyagent.supportcopilot.ticket.TicketDtos.CreateTicketRequest;
import com.cyagent.supportcopilot.ticket.TicketDtos.TicketEventResponse;
import com.cyagent.supportcopilot.ticket.TicketDtos.TicketResponse;
import com.cyagent.supportcopilot.ticket.TicketDtos.UpdateTicketRequest;

@Service
public class TicketService {

	private static final AtomicInteger TICKET_SEQUENCE = new AtomicInteger(10100);

	private final TicketRepository ticketRepository;
	private final AnalysisService analysisService;

	public TicketService(TicketRepository ticketRepository, AnalysisService analysisService) {
		this.ticketRepository = ticketRepository;
		this.analysisService = analysisService;
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
		return toResponse(ticketRepository.save(ticket));
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
		var events = latest == null
			? List.of(new TicketEventResponse("created-" + ticket.getId(), "工单创建", "已进入待处理队列", ticket.getCreatedAt()))
			: List.of(
				new TicketEventResponse("created-" + ticket.getId(), "工单创建", "已进入待处理队列", ticket.getCreatedAt()),
				new TicketEventResponse("analysis-" + latest.id(), "辅助分析完成", latest.decision().reason(), latest.createdAt())
			);

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
			latest,
			events
		);
	}
}
