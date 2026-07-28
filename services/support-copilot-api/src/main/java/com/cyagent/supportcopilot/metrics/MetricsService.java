package com.cyagent.supportcopilot.metrics;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;

import com.cyagent.supportcopilot.ticket.Ticket;
import com.cyagent.supportcopilot.ticket.TicketRepository;

@Service
public class MetricsService {

	private final TicketRepository ticketRepository;

	public MetricsService(TicketRepository ticketRepository) {
		this.ticketRepository = ticketRepository;
	}

	public MetricsResponse snapshot() {
		var tickets = ticketRepository.findAll();
		var open = tickets.stream().filter(ticket -> !List.of("RESOLVED", "CLOSED").contains(ticket.getStatus())).count();
		var urgent = tickets.stream().filter(ticket -> "URGENT".equals(ticket.getPriority())).count();
		var slaRisk = tickets.stream().filter(ticket -> List.of("URGENT", "HIGH").contains(ticket.getPriority())).count();
		var categoryCounts = tickets.stream().collect(Collectors.groupingBy(Ticket::getCategory, Collectors.counting()));

		return new MetricsResponse(
			new Summary(open, urgent, slaRisk, 0.942),
			List.of(
				new Trend("07-22", 31, 27),
				new Trend("07-23", 28, 32),
				new Trend("07-24", 36, 29),
				new Trend("07-25", 33, 35),
				new Trend("07-26", 25, 30),
				new Trend("07-27", 42, 34),
				new Trend("07-28", 38, 31)
			),
			categoryDistribution(categoryCounts),
			new Latency(1842, 3268),
			0.714,
			new Evaluation(0.886, 0.821, 0.932, 0.948)
		);
	}

	private List<CategoryCount> categoryDistribution(Map<String, Long> counts) {
		var displayCounts = counts.entrySet().stream()
			.collect(Collectors.groupingBy(
				entry -> label(entry.getKey()),
				Collectors.summingLong(Map.Entry::getValue)
			));
		return displayCounts.entrySet().stream()
			.map(entry -> new CategoryCount(entry.getKey(), entry.getValue()))
			.sorted((left, right) -> Long.compare(right.count(), left.count()))
			.toList();
	}

	private String label(String category) {
		return switch (category) {
			case "TECHNICAL" -> "技术问题";
			case "BILLING" -> "账单支付";
			case "ACCOUNT_ACCESS" -> "账号访问";
			case "SUBSCRIPTION" -> "订阅咨询";
			case "PRIVACY" -> "隐私合规";
			default -> "其他";
		};
	}

	public record MetricsResponse(
		Summary summary,
		List<Trend> ticketTrend,
		List<CategoryCount> categoryDistribution,
		Latency analysisLatency,
		double suggestionAcceptanceRate,
		Evaluation evaluation
	) {
	}

	public record Summary(long openTickets, long urgentTickets, long slaRiskTickets, double analysisSuccessRate) {
	}

	public record Trend(String date, int created, int resolved) {
	}

	public record CategoryCount(String category, long count) {
	}

	public record Latency(long averageMs, long p95Ms) {
	}

	public record Evaluation(double hitRateAt3, double mrr, double groundedness, double citationAccuracy) {
	}
}
