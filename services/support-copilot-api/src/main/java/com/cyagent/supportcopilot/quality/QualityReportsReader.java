package com.cyagent.supportcopilot.quality;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.InvalidPathException;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import com.cyagent.supportcopilot.quality.QualityReport.Kind;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

@Component
public class QualityReportsReader {
	private static final int MAX_BYTES = 2 * 1024 * 1024;
	private final ObjectMapper mapper;
	private final String livePath;
	private final String liveDigest;
	private final String businessPath;
	private final String businessDigest;

	public QualityReportsReader(ObjectMapper mapper,
		@Value("${quality.live-report-path:${QUALITY_LIVE_REPORT_PATH:}}") String livePath,
		@Value("${quality.live-report-sha256:${QUALITY_LIVE_REPORT_SHA256:}}") String liveDigest,
		@Value("${quality.business-report-path:${QUALITY_BUSINESS_REPORT_PATH:}}") String businessPath,
		@Value("${quality.business-report-sha256:${QUALITY_BUSINESS_REPORT_SHA256:}}") String businessDigest) {
		this.mapper = mapper;
		this.livePath = livePath;
		this.liveDigest = liveDigest;
		this.businessPath = businessPath;
		this.businessDigest = businessDigest;
	}

	public Reports read() {
		return new Reports(readSlot(livePath, liveDigest, Kind.LIVE_EVALUATION),
			readSlot(businessPath, businessDigest, Kind.BUSINESS_BENCHMARK));
	}

	private Slot readSlot(String configuredPath, String digest, Kind kind) {
		if (configuredPath.isBlank() && digest.isBlank()) return Slot.unavailable(Status.NOT_CONFIGURED);
		if (configuredPath.isBlank() || !digest.matches("[a-fA-F0-9]{64}")) return Slot.unavailable(Status.INVALID);
		try {
			var path = Path.of(configuredPath);
			if (!Files.isRegularFile(path)) {
				return Slot.unavailable(Files.notExists(path) ? Status.MISSING : Status.INVALID);
			}
			byte[] bytes;
			try (var input = Files.newInputStream(path)) {
				bytes = input.readNBytes(MAX_BYTES + 1);
			}
			if (bytes.length > MAX_BYTES || !sha256(bytes).equalsIgnoreCase(digest)) return Slot.unavailable(Status.INVALID);
			return new Slot(Status.AVAILABLE, new QualityReportParser().parse(mapper.readTree(bytes), kind));
		} catch (NoSuchFileException exception) {
			return Slot.unavailable(Status.MISSING);
		} catch (IOException | InvalidPathException | JacksonException | QualityReportParser.InvalidReport exception) {
			return Slot.unavailable(Status.INVALID);
		}
	}

	private String sha256(byte[] bytes) {
		try {
			return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
		} catch (NoSuchAlgorithmException exception) {
			throw new IllegalStateException("SHA-256 is unavailable", exception);
		}
	}

	public enum Status { AVAILABLE, NOT_CONFIGURED, MISSING, INVALID }
	public record Slot(Status status, QualityReport report) {
		static Slot unavailable(Status status) { return new Slot(status, null); }
	}
	public record Reports(Slot liveEvaluation, Slot businessBenchmark) {}
}
