package com.cyagent.supportcopilot.analysis.review;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Lob;
import jakarta.persistence.Table;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "analysis_reviews")
@Getter
@Setter
@NoArgsConstructor
public class AnalysisReview {

	@Id
	private String id;

	@Column(nullable = false, length = 48)
	private String ticketId;

	@Column(nullable = false, length = 64)
	private String analysisId;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 24)
	private AnalysisReviewAction action;

	@Column(nullable = false, length = 32)
	private String reviewerType;

	@Column(nullable = false, length = 80)
	private String reviewerLabel;

	@Lob
	@Column(nullable = false)
	private String originalReplyContent;

	@Lob
	@Column(nullable = false)
	private String reviewedReplyContent;

	@Column(nullable = false)
	private long ticketVersion;

	@Column(nullable = false, length = 64)
	private String traceId;

	@Column(nullable = false, updatable = false)
	private Instant createdAt;
}
