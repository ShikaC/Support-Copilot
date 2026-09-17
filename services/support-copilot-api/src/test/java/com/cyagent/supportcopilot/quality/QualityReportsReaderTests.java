package com.cyagent.supportcopilot.quality;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.stream.Stream;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;

import tools.jackson.databind.ObjectMapper;

class QualityReportsReaderTests {
	@TempDir Path directory;
	private final ObjectMapper mapper = new ObjectMapper();
	private static final String HASH = "a".repeat(64);
	private static final String LIVE = """
		{
		  "schemaVersion":1,"id":"test-live","kind":"LIVE_EVALUATION","title":"Live regression",
		  "dataset":"synthetic","generatedAt":"2026-09-10T00:00:00Z",
		  "sourceFiles":[{"name":"docs/evidence.json","sha256":"%s"}],
		  "sampleCount":3,"distinctCaseCount":3,"humanReviewedCount":0,
		  "answerAccuracy":null,"businessResolutionRate":null,"timeSavedMinutes":null,"cost":null,
		  "outcomes":{"normalLive":1,"evidenceInsufficient":1,"timeout":1,"otherFallback":0,"error":0},
		  "metrics":[{"id":"retrieval","label":"Retrieval","value":0.5,"unit":"RATE","denominator":3,"description":"Process only"}],
		  "groups":[],
		  "failures":[
		    {"caseId":"b","concurrency":null,"outcome":"EVIDENCE_INSUFFICIENT","reason":"No evidence","traceId":"trace-b"},
		    {"caseId":"c","concurrency":null,"outcome":"TIMEOUT","reason":"ReadTimeout","traceId":null}
		  ],
		  "gateReasons":["human-review-incomplete"],"limitations":["Not accuracy"]
		}
		""".formatted(HASH);

	private static String business() {
		return LIVE.replace("LIVE_EVALUATION", "BUSINESS_BENCHMARK")
			.replace("\"concurrency\":null", "\"concurrency\":1")
			.replace("\"groups\":[]", """
				"groups":[{"concurrency":1,"total":3,"normalLive":1,"evidenceInsufficient":1,
				"timeout":1,"otherFallback":0,"error":0,"p50Ms":100,"p95Ms":200,"apiCompleted":3,"persisted":3}]
				""");
	}

	@Test
	void readsIndependentValidReportsWithoutInventingUnmeasuredMetrics() throws Exception {
		var live = write("live.json", LIVE);
		var business = write("business.json", business());
		var result = new QualityReportsReader(mapper, live.toString(), hash(LIVE), business.toString(), hash(business())).read();
		assertThat(result.liveEvaluation().status()).isEqualTo(QualityReportsReader.Status.AVAILABLE);
		assertThat(result.liveEvaluation().report().humanReviewedCount()).isZero();
		assertThat(result.liveEvaluation().report().answerAccuracy()).isNull();
		assertThat(result.businessBenchmark().report().groups().getFirst().persisted()).isEqualTo(3);
		assertThat(result.businessBenchmark().report().outcomes().normalLive()).isEqualTo(1);
		assertThat(result.businessBenchmark().report().failures()).hasSize(2);
	}

	@Test
	void readsExportedFrozenEvidenceWithItsManifestDigests() throws Exception {
		var evidence = Path.of("../../docs/verification/product-quality-center-2026-09-10/reports");
		var manifest = mapper.readTree(Files.readAllBytes(evidence.resolve("manifest.json")));
		var result = new QualityReportsReader(mapper, evidence.resolve("live.json").toString(),
			manifest.get("files").get(0).get("sha256").asString(), evidence.resolve("business.json").toString(),
			manifest.get("files").get(1).get("sha256").asString()).read();
		assertThat(result.liveEvaluation().status()).isEqualTo(QualityReportsReader.Status.AVAILABLE);
		assertThat(result.businessBenchmark().status()).isEqualTo(QualityReportsReader.Status.AVAILABLE);
		assertThat(result.liveEvaluation().report().sampleCount()).isEqualTo(22);
		assertThat(result.liveEvaluation().report().outcomes()).isEqualTo(new QualityReport.Outcomes(17, 3, 2, 0, 0));
		assertThat(result.businessBenchmark().report().sampleCount()).isEqualTo(96);
		assertThat(result.businessBenchmark().report().distinctCaseCount()).isEqualTo(32);
		assertThat(result.businessBenchmark().report().outcomes()).isEqualTo(new QualityReport.Outcomes(64, 14, 18, 0, 0));
		assertThat(result.businessBenchmark().report().failures()).hasSize(32);
	}

	@Test
	void leavesUnconfiguredSlotsExplicitlyEmpty() {
		var result = new QualityReportsReader(mapper, "", "", "", "").read();
		assertThat(result.liveEvaluation().status()).isEqualTo(QualityReportsReader.Status.NOT_CONFIGURED);
		assertThat(result.businessBenchmark().report()).isNull();
	}

	@Test
	void namesMissingSeparatelyAndNeverExposesTheConfiguredPath() throws Exception {
		var result = new QualityReportsReader(mapper, directory.resolve("sensitive-path").toString(), HASH, "", "").read();
		assertThat(result.liveEvaluation().status()).isEqualTo(QualityReportsReader.Status.MISSING);
		assertThat(mapper.writeValueAsString(result)).doesNotContain(directory.toString(), "sensitive-path");
	}

	@Test
	void digestTamperMakesOnlyOneSlotInvalid() throws Exception {
		var live = write("live.json", LIVE);
		var business = write("business.json", business());
		var result = new QualityReportsReader(mapper, live.toString(), HASH, business.toString(), hash(business())).read();
		assertThat(result.liveEvaluation().status()).isEqualTo(QualityReportsReader.Status.INVALID);
		assertThat(result.liveEvaluation().report()).isNull();
		assertThat(result.businessBenchmark().status()).isEqualTo(QualityReportsReader.Status.AVAILABLE);
	}

	@Test
	void rejectsOversizedFilesBeforeParsing() throws Exception {
		var oversized = LIVE + " ".repeat(2 * 1024 * 1024);
		assertInvalid(oversized);
	}

	@Test
	void requiresPathAndExpectedDigestTogether() throws Exception {
		var path = write("live.json", LIVE).toString();
		assertThat(new QualityReportsReader(mapper, path, "", "", HASH).read().liveEvaluation().status())
			.isEqualTo(QualityReportsReader.Status.INVALID);
		assertThat(new QualityReportsReader(mapper, path, "", "", HASH).read().businessBenchmark().status())
			.isEqualTo(QualityReportsReader.Status.INVALID);
	}

	@Test
	void unknownProgrammingErrorsRemainRealErrors() throws Exception {
		var brokenMapper = mock(ObjectMapper.class);
		var bytes = LIVE.getBytes(StandardCharsets.UTF_8);
		when(brokenMapper.readTree(bytes)).thenThrow(new IllegalStateException("programming defect"));
		var path = write("live.json", LIVE);
		assertThatThrownBy(() -> new QualityReportsReader(brokenMapper, path.toString(), hash(LIVE), "", "").read())
			.isInstanceOf(IllegalStateException.class).hasMessage("programming defect");
	}

	@ParameterizedTest
	@MethodSource("invalidReports")
	void rejectsMalformedOrIncoherentEvidence(String report) throws Exception {
		assertInvalid(report);
	}

	private static Stream<String> invalidReports() {
		return Stream.of(
			"{", "null", "[]", LIVE.replace("\"schemaVersion\":1", "\"schemaVersion\":2"),
			LIVE.replace("\"sampleCount\":3", "\"sampleCount\":4294967299"),
			LIVE.replace("\"sampleCount\":3", "\"sampleCount\":\"3\""),
			LIVE.replace("\"sampleCount\":3", "\"sampleCount\":4"),
			LIVE.replace("\"distinctCaseCount\":3", "\"distinctCaseCount\":4"),
			LIVE.replace("\"humanReviewedCount\":0", "\"humanReviewedCount\":4"),
			LIVE.replace("\"humanReviewedCount\":0", "\"humanReviewedCount\":1"),
			LIVE.replace("\"answerAccuracy\":null", "\"answerAccuracy\":0.99"),
			LIVE.replace("\"cost\":null,", ""),
			LIVE.replace("\"value\":0.5", "\"value\":1.1"),
			LIVE.replace("\"value\":0.5", "\"value\":-1"),
			LIVE.replace("\"value\":0.5", "\"value\":1e999"),
			LIVE.replace("\"denominator\":3", "\"denominator\":0"),
			LIVE.replace("\"denominator\":3", "\"denominator\":4"),
			LIVE.replace("docs/evidence.json", "/private/evidence.json"),
			LIVE.replace("docs/evidence.json", "docs/../evidence.json"),
			LIVE.replace("docs/evidence.json", "docs//evidence.json"),
			LIVE.replace(HASH, "invalid-hash"),
			LIVE.replace("2026-09-10T00:00:00Z", "yesterday"),
			LIVE.replace("\"caseId\":\"c\"", "\"caseId\":\"b\""),
			LIVE.replace("\"outcome\":\"TIMEOUT\"", "\"outcome\":\"ERROR\""),
			LIVE.replace("\"outcome\":\"TIMEOUT\"", "\"outcome\":\"SUCCEEDED\""),
			LIVE.replace("\"concurrency\":null", "\"concurrency\":1"),
			LIVE.replace("LIVE_EVALUATION", "BUSINESS_BENCHMARK")
		);
	}

	@ParameterizedTest
	@MethodSource("invalidBusinessReports")
	void rejectsIncoherentGroupAndFailureTotals(String report) throws Exception {
		var path = write("business.json", report);
		var result = new QualityReportsReader(mapper, "", "", path.toString(), hash(report)).read();
		assertThat(result.businessBenchmark().status()).isEqualTo(QualityReportsReader.Status.INVALID);
	}

	private static Stream<String> invalidBusinessReports() {
		return Stream.of(
			business().replace("\"total\":3", "\"total\":4"),
			business().replace("\"p50Ms\":100", "\"p50Ms\":300"),
			business().replace("\"persisted\":3", "\"persisted\":4"),
			business().replace("\"concurrency\":1,\"outcome\"", "\"concurrency\":2,\"outcome\""),
			business().replace("\"p95Ms\":200", "\"p95Ms\":-1")
		);
	}

	private void assertInvalid(String report) throws Exception {
		var path = write("invalid.json", report);
		var result = new QualityReportsReader(mapper, path.toString(), hash(report), "", "").read();
		assertThat(result.liveEvaluation().status()).isEqualTo(QualityReportsReader.Status.INVALID);
		assertThat(result.liveEvaluation().report()).isNull();
	}

	private Path write(String name, String contents) throws Exception {
		return Files.writeString(directory.resolve(name), contents);
	}

	private String hash(String contents) throws Exception {
		return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(contents.getBytes(StandardCharsets.UTF_8)));
	}
}
