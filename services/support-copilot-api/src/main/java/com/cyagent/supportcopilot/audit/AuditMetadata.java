package com.cyagent.supportcopilot.audit;

import java.util.Comparator;
import java.util.List;

import com.cyagent.supportcopilot.analysis.FallbackReason;

public sealed interface AuditMetadata permits AuditMetadata.None,
	AuditMetadata.TicketChange, AuditMetadata.Analysis, AuditMetadata.Review,
	AuditMetadata.KnowledgeRelease {

	enum AnalysisMode {
		FALLBACK,
		LIVE,
		MOCK;

		public static AnalysisMode parse(String value) {
			try {
				return valueOf(value.toUpperCase(java.util.Locale.ROOT));
			} catch (NullPointerException | IllegalArgumentException exception) {
				throw new IllegalArgumentException("Audit analysis mode is invalid.", exception);
			}
		}
	}

	enum AnalysisStatus {
		FALLBACK,
		SUCCEEDED;

		public static AnalysisStatus parse(String value) {
			try {
				return valueOf(value);
			} catch (NullPointerException | IllegalArgumentException exception) {
				throw new IllegalArgumentException("Audit analysis status is invalid.", exception);
			}
		}
	}

	enum ReviewAction {
		APPROVED,
		EDITED,
		REJECTED
	}

	record None() implements AuditMetadata {
	}

	record TicketChange(List<AuditChangedField> changedFields) implements AuditMetadata {

		public TicketChange {
			changedFields = changedFields.stream().distinct()
				.sorted(Comparator.comparing(Enum::name)).toList();
		}
	}

	record Analysis(
		AnalysisMode mode,
		AnalysisStatus status,
		FallbackReason fallbackCategory,
		long sourceVersion,
		String resultId
	) implements AuditMetadata {

		public Analysis {
			requireResultId(resultId);
		}
	}

	record Review(ReviewAction reviewAction, long sourceVersion, String resultId) implements AuditMetadata {

		public Review {
			requireResultId(resultId);
		}
	}

	record KnowledgeRelease(
		String releaseId,
		int releaseVersion,
		String corpusChecksum,
		List<String> allowedScopes,
		String status
	) implements AuditMetadata {

		public KnowledgeRelease {
			requireResultId(releaseId);
			if (releaseVersion <= 0 || corpusChecksum == null || !corpusChecksum.matches("[a-f0-9]{64}")) {
				throw new IllegalArgumentException("Audit knowledge release identity is invalid.");
			}
			allowedScopes = List.copyOf(allowedScopes);
		}
	}

	private static void requireResultId(String value) {
		if (value == null || !value.matches("[A-Za-z0-9][A-Za-z0-9._:-]{0,254}")) {
			throw new IllegalArgumentException("Audit result id is invalid.");
		}
	}
}
