package com.cyagent.supportcopilot.metrics;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.cyagent.supportcopilot.ticket.TicketRepository;
import com.cyagent.supportcopilot.analysis.AnalysisRunRepository;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewAction;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewRepository;

@Service
public class MetricsService {

	private final TicketRepository ticketRepository;
	private final AnalysisRunRepository analysisRunRepository;
	private final AnalysisReviewRepository analysisReviewRepository;
	private final EvaluationReportReader evaluationReportReader;

	public MetricsService(
		TicketRepository ticketRepository,
		AnalysisRunRepository analysisRunRepository,
		AnalysisReviewRepository analysisReviewRepository,
		EvaluationReportReader evaluationReportReader
	) {
		this.ticketRepository = ticketRepository;
		this.analysisRunRepository = analysisRunRepository;
		this.analysisReviewRepository = analysisReviewRepository;
		this.evaluationReportReader = evaluationReportReader;
	}

	@Transactional(readOnly = true)
	public MetricsResponse snapshot() {
		var open = ticketRepository.countByStatusNotIn(List.of("RESOLVED", "CLOSED"));
		var urgent = ticketRepository.countByPriority("URGENT");
		var slaRisk = urgent + ticketRepository.countByPriority("HIGH");
		var categoryCounts = ticketRepository.countByCategory().stream()
			.collect(Collectors.toMap(
				TicketRepository.CategoryCountProjection::getCategory,
				projection -> projection.getCount()
			));
		var totalAnalysisRuns = analysisRunRepository.count();
		var analysisSuccessRate = totalAnalysisRuns == 0
			? null
			: analysisRunRepository.countByStatus("SUCCEEDED") / (double) totalAnalysisRuns;
		var totalReviews = analysisReviewRepository.count();
		var suggestionAcceptanceRate = totalReviews == 0
			? null
			: analysisReviewRepository.countByActionIn(List.of(
				AnalysisReviewAction.APPROVED,
				AnalysisReviewAction.EDITED
			)) / (double) totalReviews;

		var evaluation = evaluationReportReader.read()
			.map(this::toEvaluation)
			.orElse(null);

		return new MetricsResponse(
			new Summary(open, urgent, slaRisk, analysisSuccessRate),
			List.of(),
			categoryDistribution(categoryCounts),
			null,
			suggestionAcceptanceRate,
			evaluation
		);
	}

	private Evaluation toEvaluation(EvaluationReportReader.EvaluationSnapshot report) {
		return new Evaluation(
			report.datasetName(),
			report.mode(),
			report.modelName(),
			report.promptVersion(),
			report.totalCases(),
			report.topN(),
			report.topK(),
			report.hitRateAtK(),
			report.mrr(),
			report.citationCoverage(),
			report.noEvidenceSafetyRate(),
			report.averageDurationMs(),
			report.p95DurationMs(),
			report.thresholdFailureCount(),
			report.passed(),
			report.generatedAt()
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
			.sorted((left, right) -> {
				var countComparison = Long.compare(right.count(), left.count());
				return countComparison != 0 ? countComparison : left.category().compareTo(right.category());
			})
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
		Double suggestionAcceptanceRate,
		Evaluation evaluation
	) {
	}

	public record Summary(long openTickets, long urgentTickets, long slaRiskTickets, Double analysisSuccessRate) {
	}

	public record Trend(String date, int created, int resolved) {
	}

	public record CategoryCount(String category, long count) {
	}

	public record Latency(long averageMs, long p95Ms) {
	}

	public record Evaluation(
		String datasetName,
		String mode,
		String modelName,
		String promptVersion,
		int totalCases,
		int topN,
		int topK,
		double hitRateAtK,
		double mrr,
		double citationCoverage,
		double noEvidenceSafetyRate,
		double averageDurationMs,
		int p95DurationMs,
		int thresholdFailureCount,
		boolean passed,
		java.time.Instant generatedAt
	) {
	}
}
