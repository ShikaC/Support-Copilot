package com.cyagent.supportcopilot.ticket;

import java.util.List;

import jakarta.validation.Valid;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.cyagent.supportcopilot.analysis.AnalysisResponse;
import com.cyagent.supportcopilot.analysis.AnalysisService;
import com.cyagent.supportcopilot.ticket.TicketDtos.CreateTicketRequest;
import com.cyagent.supportcopilot.ticket.TicketDtos.TicketResponse;
import com.cyagent.supportcopilot.ticket.TicketDtos.UpdateTicketRequest;

@RestController
@RequestMapping("/api/tickets")
public class TicketController {

	private final TicketService ticketService;
	private final AnalysisService analysisService;

	public TicketController(TicketService ticketService, AnalysisService analysisService) {
		this.ticketService = ticketService;
		this.analysisService = analysisService;
	}

	@GetMapping
	List<TicketResponse> list(
		@RequestParam(required = false) String status,
		@RequestParam(required = false) String priority,
		@RequestParam(required = false) String keyword
	) {
		return ticketService.list(status, priority, keyword);
	}

	@GetMapping("/{id}")
	TicketResponse get(@PathVariable String id) {
		return ticketService.get(id);
	}

	@PostMapping
	@ResponseStatus(HttpStatus.CREATED)
	TicketResponse create(@Valid @RequestBody CreateTicketRequest request) {
		return ticketService.create(request);
	}

	@PatchMapping("/{id}")
	TicketResponse update(@PathVariable String id, @RequestBody UpdateTicketRequest request) {
		return ticketService.update(id, request);
	}

	@PostMapping("/{id}/analyze")
	AnalysisResponse analyze(@PathVariable String id) {
		return analysisService.analyze(id);
	}

	@GetMapping("/{id}/analyses")
	List<AnalysisResponse> analyses(@PathVariable String id) {
		return analysisService.history(id);
	}
}
