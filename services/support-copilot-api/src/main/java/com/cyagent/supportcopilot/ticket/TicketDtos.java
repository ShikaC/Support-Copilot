package com.cyagent.supportcopilot.ticket;

import java.time.Instant;
import java.util.List;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import com.cyagent.supportcopilot.analysis.AnalysisResponse;

public final class TicketDtos {

	private TicketDtos() {
	}

	public record CreateTicketRequest(
		@NotBlank String channel,
		@NotBlank @Size(max = 80) String customerName,
		@NotBlank @Size(max = 120) String customerCompany,
		@NotBlank String customerTier,
		@NotBlank @Size(max = 240) String subject,
		@NotBlank @Size(max = 4000) String description,
		String language
	) {
	}

	public record UpdateTicketRequest(
		String status,
		String priority,
		String category,
		String assigneeName
	) {
	}

	public record TicketEventResponse(
		String id,
		String label,
		String detail,
		Instant createdAt
	) {
	}

	public record TicketResponse(
		String id,
		String ticketNo,
		String channel,
		String customerName,
		String customerCompany,
		String customerTier,
		String subject,
		String description,
		String language,
		String category,
		String priority,
		String status,
		String assigneeName,
		Instant slaDeadline,
		Instant createdAt,
		Instant updatedAt,
		AnalysisResponse latestAnalysis,
		List<TicketEventResponse> events
	) {
	}
}
