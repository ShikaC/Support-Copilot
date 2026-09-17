package com.cyagent.supportcopilot.quality;

import java.time.Instant;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.function.Function;

import com.cyagent.supportcopilot.quality.QualityReport.Failure;
import com.cyagent.supportcopilot.quality.QualityReport.FailureOutcome;
import com.cyagent.supportcopilot.quality.QualityReport.Group;
import com.cyagent.supportcopilot.quality.QualityReport.Kind;
import com.cyagent.supportcopilot.quality.QualityReport.Metric;
import com.cyagent.supportcopilot.quality.QualityReport.Outcomes;
import com.cyagent.supportcopilot.quality.QualityReport.SourceFile;
import com.cyagent.supportcopilot.quality.QualityReport.Unit;

import tools.jackson.databind.JsonNode;

final class QualityReportParser {
	static final class InvalidReport extends RuntimeException {}

	QualityReport parse(JsonNode root, Kind expectedKind) {
		require(root != null && root.isObject());
		require(integer(root, "schemaVersion", 1) == 1);
		var kind = enumeration(root, "kind", Kind.class);
		require(kind == expectedKind);
		var generatedAt = text(root, "generatedAt");
		try {
			require(generatedAt.endsWith("Z"));
			Instant.parse(generatedAt);
		} catch (DateTimeParseException exception) {
			throw new InvalidReport();
		}
		var sources = list(root, "sourceFiles", item -> {
			var name = text(item, "name");
			require(!name.startsWith("/") && !name.contains("\\") && !name.contains(":")
				&& !List.of(name.split("/", -1)).contains("..")
				&& !List.of(name.split("/", -1)).contains(".")
				&& !List.of(name.split("/", -1)).contains(""));
			var digest = text(item, "sha256");
			require(digest.matches("[a-fA-F0-9]{64}"));
			return new SourceFile(name, digest);
		});
		require(!sources.isEmpty());
		unique(sources.stream().map(SourceFile::name).toList());
		int sampleCount = integer(root, "sampleCount", 1);
		int distinct = integer(root, "distinctCaseCount", 1);
		int humanReviewed = integer(root, "humanReviewedCount", 0);
		require(distinct <= sampleCount && humanReviewed == 0);
		for (var field : List.of("answerAccuracy", "businessResolutionRate", "timeSavedMinutes", "cost")) {
			require(required(root, field).isNull());
		}
		var outcomes = outcomes(required(root, "outcomes"));
		require(outcomes.total() == sampleCount);
		var metrics = list(root, "metrics", item -> {
			var value = nullableNumber(item, "value");
			var unit = enumeration(item, "unit", Unit.class);
			require(value == null || unit != Unit.RATE || value <= 1);
			var denominator = nullablePositiveInt(item, "denominator");
			require(denominator == null || denominator <= sampleCount);
			return new Metric(text(item, "id"), text(item, "label"), value, unit,
				denominator, text(item, "description"));
		});
		unique(metrics.stream().map(Metric::id).toList());
		var groups = list(root, "groups", this::group);
		require(expectedKind == Kind.BUSINESS_BENCHMARK ? !groups.isEmpty() : groups.isEmpty());
		unique(groups.stream().map(Group::concurrency).toList());
		if (!groups.isEmpty()) {
			require(groups.stream().mapToLong(Group::total).sum() == sampleCount);
			require(groups.stream().mapToLong(Group::normalLive).sum() == outcomes.normalLive());
			require(groups.stream().mapToLong(Group::evidenceInsufficient).sum() == outcomes.evidenceInsufficient());
			require(groups.stream().mapToLong(Group::timeout).sum() == outcomes.timeout());
			require(groups.stream().mapToLong(Group::otherFallback).sum() == outcomes.otherFallback());
			require(groups.stream().mapToLong(Group::error).sum() == outcomes.error());
		}
		var failures = list(root, "failures", item -> new Failure(text(item, "caseId"),
			nullablePositiveInt(item, "concurrency"), enumeration(item, "outcome", FailureOutcome.class),
			text(item, "reason"), nullableText(item, "traceId")));
		var failureKeys = new HashSet<List<Object>>();
		for (var failure : failures) {
			require(failureKeys.add(List.of(failure.caseId(), failure.concurrency() == null ? 0 : failure.concurrency())));
			require(expectedKind == Kind.LIVE_EVALUATION ? failure.concurrency() == null
				: failure.concurrency() != null && groups.stream().anyMatch(g -> g.concurrency() == failure.concurrency()));
		}
		validateFailureCounts(failures, outcomes);
		for (var group : groups) {
			validateFailureCounts(failures.stream().filter(f -> f.concurrency() == group.concurrency()).toList(),
				new Outcomes(group.normalLive(), group.evidenceInsufficient(), group.timeout(), group.otherFallback(), group.error()));
		}
		return new QualityReport(1, text(root, "id"), kind, text(root, "title"), text(root, "dataset"),
			generatedAt, sources, sampleCount, distinct, humanReviewed, null, null, null, null,
			outcomes, metrics, groups, failures, strings(root, "gateReasons"), strings(root, "limitations"));
	}

	private Group group(JsonNode node) {
		var total = integer(node, "total", 1);
		var outcomes = outcomes(node);
		require(outcomes.total() == total);
		var p50 = number(node, "p50Ms");
		var p95 = number(node, "p95Ms");
		require(p50 <= p95);
		var apiCompleted = integer(node, "apiCompleted", 0);
		var persisted = integer(node, "persisted", 0);
		require(apiCompleted <= total && persisted <= apiCompleted);
		return new Group(integer(node, "concurrency", 1), total, outcomes.normalLive(), outcomes.evidenceInsufficient(),
			outcomes.timeout(), outcomes.otherFallback(), outcomes.error(), p50, p95, apiCompleted, persisted);
	}

	private void validateFailureCounts(List<Failure> failures, Outcomes outcomes) {
		require(failures.size() == outcomes.total() - outcomes.normalLive());
		require(count(failures, FailureOutcome.EVIDENCE_INSUFFICIENT) == outcomes.evidenceInsufficient());
		require(count(failures, FailureOutcome.TIMEOUT) == outcomes.timeout());
		require(count(failures, FailureOutcome.OTHER_FALLBACK) == outcomes.otherFallback());
		require(count(failures, FailureOutcome.ERROR) == outcomes.error());
	}

	private long count(List<Failure> failures, FailureOutcome outcome) {
		return failures.stream().filter(f -> f.outcome() == outcome).count();
	}

	private Outcomes outcomes(JsonNode node) {
		return new Outcomes(integer(node, "normalLive", 0), integer(node, "evidenceInsufficient", 0),
			integer(node, "timeout", 0), integer(node, "otherFallback", 0), integer(node, "error", 0));
	}

	private <T> List<T> list(JsonNode parent, String field, Function<JsonNode, T> parse) {
		var node = required(parent, field);
		require(node.isArray());
		var result = new ArrayList<T>();
		for (var item : node) result.add(parse.apply(item));
		return List.copyOf(result);
	}

	private List<String> strings(JsonNode parent, String field) {
		return list(parent, field, this::textValue);
	}

	private <T> void unique(List<T> values) {
		require(new HashSet<>(values).size() == values.size());
	}

	private <E extends Enum<E>> E enumeration(JsonNode parent, String field, Class<E> type) {
		var value = text(parent, field);
		try {
			return Enum.valueOf(type, value);
		} catch (IllegalArgumentException exception) {
			throw new InvalidReport();
		}
	}

	private Integer nullablePositiveInt(JsonNode parent, String field) {
		return required(parent, field).isNull() ? null : integer(parent, field, 1);
	}

	private int integer(JsonNode parent, String field, int minimum) {
		var node = required(parent, field);
		require(node.isIntegralNumber() && node.canConvertToInt());
		var value = node.asInt();
		require(value >= minimum);
		return value;
	}

	private Double nullableNumber(JsonNode parent, String field) {
		return required(parent, field).isNull() ? null : number(parent, field);
	}

	private double number(JsonNode parent, String field) {
		var node = required(parent, field);
		require(node.isNumber());
		var value = node.asDouble();
		require(Double.isFinite(value) && value >= 0);
		return value;
	}

	private String nullableText(JsonNode parent, String field) {
		return required(parent, field).isNull() ? null : text(parent, field);
	}

	private String text(JsonNode parent, String field) {
		return textValue(required(parent, field));
	}

	private String textValue(JsonNode node) {
		require(node.isString() && !node.asString().isBlank());
		return node.asString();
	}

	private JsonNode required(JsonNode parent, String field) {
		require(parent != null && parent.isObject());
		var node = parent.get(field);
		require(node != null);
		return node;
	}

	private void require(boolean condition) {
		if (!condition) throw new InvalidReport();
	}
}
