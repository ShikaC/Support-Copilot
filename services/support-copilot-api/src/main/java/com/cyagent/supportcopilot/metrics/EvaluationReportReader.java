package com.cyagent.supportcopilot.metrics;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.Optional;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Component
public class EvaluationReportReader {

	private static final Logger LOGGER = LoggerFactory.getLogger(EvaluationReportReader.class);

	private final ObjectMapper objectMapper;
	private final Path reportPath;

	@Autowired
	public EvaluationReportReader(
		ObjectMapper objectMapper,
		@Value("${evaluation.report-path:../support-copilot-ai/evaluation/reports/mock-latest.json}") String reportPath
	) {
		this(objectMapper, Path.of(reportPath));
	}

	EvaluationReportReader(ObjectMapper objectMapper, Path reportPath) {
		this.objectMapper = objectMapper;
		this.reportPath = reportPath;
	}

	public Optional<EvaluationSnapshot> read() {
		if (!Files.isRegularFile(reportPath)) {
			return Optional.empty();
		}

		try {
			var root = objectMapper.readTree(Files.readString(reportPath, StandardCharsets.UTF_8));
			return Optional.of(parse(root));
		} catch (IOException | RuntimeException exception) {
			LOGGER.warn("Evaluation report is unavailable: {}", exception.getMessage());
			return Optional.empty();
		}
	}

	private EvaluationSnapshot parse(JsonNode root) {
		var reportKind = root.get("report_kind");
		if (reportKind != null && reportKind.isString() && reportKind.asString().equals("live-evaluation")) {
			return parseLive(root);
		}
		var metrics = requiredObject(root, "metrics");
		var thresholdFailures = requiredArray(root, "threshold_failures");
		var topN = requiredPositiveInt(root, "top_n");
		var topK = requiredPositiveInt(root, "top_k");
		if (topK > topN) {
			throw new IllegalArgumentException("top_k must not exceed top_n");
		}
		return new EvaluationSnapshot(
			requiredText(root, "dataset_name"),
			requiredMode(root),
			requiredFirstText(root, "model_names"),
			requiredFirstText(root, "prompt_versions"),
			requiredPositiveInt(metrics, "total_cases"),
			topN,
			topK,
			requiredRate(metrics, "hit_rate_at_k"),
			requiredRate(metrics, "mrr"),
			requiredRate(metrics, "citation_coverage"),
			requiredRate(metrics, "no_evidence_safety_rate"),
			requiredNonNegativeDouble(metrics, "average_duration_ms"),
			requiredNonNegativeInt(metrics, "p95_duration_ms"),
			thresholdFailures.size(),
			requiredBoolean(root, "passed"),
			Instant.parse(requiredText(root, "generated_at"))
		);
	}

	private EvaluationSnapshot parseLive(JsonNode root) {
		var run = requiredObject(root, "run");
		var provenance = requiredObject(root, "provenance");
		var summary = requiredObject(root, "summary");
		var topN = requiredPositiveInt(run, "top_n");
		var topK = requiredPositiveInt(run, "top_k");
		if (topK > topN) {
			throw new IllegalArgumentException("top_k must not exceed top_n");
		}
		return new EvaluationSnapshot(
			requiredText(run, "dataset_id") + "@" + requiredText(run, "dataset_version"),
			"live",
			requiredText(provenance, "chat_model"),
			requiredText(run, "prompt_version"),
			requiredPositiveInt(summary, "total_cases"),
			topN,
			topK,
			requiredRate(summary, "retrieval_success_rate"),
			requiredRate(summary, "mean_reciprocal_rank"),
			requiredRate(summary, "citation_valid_rate"),
			requiredRate(summary, "no_evidence_safety_rate"),
			requiredNonNegativeDouble(summary, "average_latency_ms"),
			requiredNonNegativeInt(summary, "p95_latency_ms"),
			requiredArray(summary, "gate_reasons").size(),
			requiredBoolean(summary, "publishable"),
			Instant.parse(requiredText(run, "timestamp"))
		);
	}

	private JsonNode requiredObject(JsonNode parent, String field) {
		var node = required(parent, field);
		if (!node.isObject()) {
			throw new IllegalArgumentException(field + " must be an object");
		}
		return node;
	}

	private JsonNode requiredArray(JsonNode parent, String field) {
		var node = required(parent, field);
		if (!node.isArray()) {
			throw new IllegalArgumentException(field + " must be an array");
		}
		return node;
	}

	private String requiredText(JsonNode parent, String field) {
		var node = required(parent, field);
		if (!node.isString() || node.asString().isBlank()) {
			throw new IllegalArgumentException(field + " must be a non-blank string");
		}
		return node.asString();
	}

	private String requiredFirstText(JsonNode parent, String field) {
		var array = requiredArray(parent, field);
		if (array.isEmpty() || !array.get(0).isString() || array.get(0).asString().isBlank()) {
			throw new IllegalArgumentException(field + " must contain a non-blank string");
		}
		return array.get(0).asString();
	}

	private int requiredInt(JsonNode parent, String field) {
		var node = required(parent, field);
		if (!node.isIntegralNumber()) {
			throw new IllegalArgumentException(field + " must be an integer");
		}
		return node.asInt();
	}

	private int requiredPositiveInt(JsonNode parent, String field) {
		var value = requiredInt(parent, field);
		if (value <= 0) {
			throw new IllegalArgumentException(field + " must be positive");
		}
		return value;
	}

	private int requiredNonNegativeInt(JsonNode parent, String field) {
		var value = requiredInt(parent, field);
		if (value < 0) {
			throw new IllegalArgumentException(field + " must be non-negative");
		}
		return value;
	}

	private double requiredDouble(JsonNode parent, String field) {
		var node = required(parent, field);
		if (!node.isNumber()) {
			throw new IllegalArgumentException(field + " must be a number");
		}
		return node.asDouble();
	}

	private double requiredRate(JsonNode parent, String field) {
		var value = requiredDouble(parent, field);
		if (!Double.isFinite(value) || value < 0 || value > 1) {
			throw new IllegalArgumentException(field + " must be between 0 and 1");
		}
		return value;
	}

	private double requiredNonNegativeDouble(JsonNode parent, String field) {
		var value = requiredDouble(parent, field);
		if (!Double.isFinite(value) || value < 0) {
			throw new IllegalArgumentException(field + " must be non-negative");
		}
		return value;
	}

	private String requiredMode(JsonNode root) {
		var mode = requiredText(root, "mode");
		if (!mode.equals("mock") && !mode.equals("live")) {
			throw new IllegalArgumentException("mode must be mock or live");
		}
		return mode;
	}

	private boolean requiredBoolean(JsonNode parent, String field) {
		var node = required(parent, field);
		if (!node.isBoolean()) {
			throw new IllegalArgumentException(field + " must be a boolean");
		}
		return node.asBoolean();
	}

	private JsonNode required(JsonNode parent, String field) {
		var node = parent.get(field);
		if (node == null || node.isNull()) {
			throw new IllegalArgumentException("missing " + field);
		}
		return node;
	}

	public record EvaluationSnapshot(
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
		Instant generatedAt
	) {
	}
}
