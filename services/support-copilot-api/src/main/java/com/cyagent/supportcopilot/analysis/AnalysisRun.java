package com.cyagent.supportcopilot.analysis;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

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

	@Column(nullable = false)
	private long sourceTicketVersion;

	@Column(nullable = false, length = 64)
	private String traceId;

	@Column(nullable = false, length = 24)
	private String status;

	@Column(nullable = false, length = 24)
	private String mode;

	@Enumerated(EnumType.STRING)
	@Column(length = 64)
	private FallbackReason fallbackReason;

	@JdbcTypeCode(SqlTypes.VARCHAR)
	@Column(nullable = false, columnDefinition = "LONGTEXT")
	private String responseJson;

	@Column(nullable = false)
	private Instant createdAt;
}
