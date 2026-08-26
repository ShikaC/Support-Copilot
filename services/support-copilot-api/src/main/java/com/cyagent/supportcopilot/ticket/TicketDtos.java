package com.cyagent.supportcopilot.ticket;

import java.time.Instant;
import java.util.List;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;

import com.cyagent.supportcopilot.analysis.AnalysisResponse;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewDtos.AnalysisReviewResponse;
import com.cyagent.supportcopilot.ticket.TicketDomain.Category;
import com.cyagent.supportcopilot.ticket.TicketDomain.Channel;
import com.cyagent.supportcopilot.ticket.TicketDomain.CustomerTier;
import com.cyagent.supportcopilot.ticket.TicketDomain.Priority;
import com.cyagent.supportcopilot.ticket.TicketDomain.Status;

public final class TicketDtos {

	private TicketDtos() {
	}

	public record CreateTicketRequest(
		@NotNull Channel channel,
		@NotBlank @Size(max = 80) String customerName,
		@NotBlank @Size(max = 120) String customerCompany,
		@NotNull CustomerTier customerTier,
		@NotBlank @Size(max = 240) String subject,
		@NotBlank @Size(max = 4000) String description,
		String language
	) {
	}

	public record UpdateTicketRequest(
		Status status,
		Priority priority,
		Category category,
		@Size(max = 80) String assigneeName,
		@NotNull @PositiveOrZero Long expectedVersion
	) {
	}

	public record UnassignTicketRequest(
		@NotNull @PositiveOrZero Long expectedVersion
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
		long version,
		AnalysisResponse latestAnalysis,
		AnalysisReviewResponse latestReview,
		List<TicketEventResponse> events
	) {
	}
}
