package com.cyagent.supportcopilot.analysis;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Lob;
import jakarta.persistence.Table;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "analysis_runs")
@Getter
@Setter
@NoArgsConstructor
public class AnalysisRun {

	@Id
	private String id;

	@Column(nullable = false, length = 48)
	private String ticketId;

	@Column(nullable = false, length = 64)
	private String traceId;

	@Column(nullable = false, length = 24)
	private String status;

	@Column(nullable = false, length = 24)
	private String mode;

	@Lob
	@Column(nullable = false)
	private String responseJson;

	@Column(nullable = false)
	private Instant createdAt;
}
