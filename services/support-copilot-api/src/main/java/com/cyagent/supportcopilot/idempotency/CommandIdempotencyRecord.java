package com.cyagent.supportcopilot.idempotency;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(
	name = "command_idempotency",
	uniqueConstraints = @UniqueConstraint(name = "uk_command_idempotency_key", columnNames = "idempotency_key")
)
@Getter
@Setter
@NoArgsConstructor
public class CommandIdempotencyRecord {

	@Id
	@Column(length = 64)
	private String id;

	@Column(nullable = false, length = 128)
	private String idempotencyKey;

	@JdbcTypeCode(SqlTypes.CHAR)
	@Column(nullable = false, length = 64)
	private String requestFingerprint;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 32)
	private CommandType commandType;

	@Column(nullable = false, length = 160)
	private String routeScope;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 16)
	private CommandStatus status;

	@Column(length = 64)
	private String ownerToken;

	@Column
	private Instant leaseExpiresAt;

	@Column
	private Integer responseHttpStatus;

	@JdbcTypeCode(SqlTypes.VARCHAR)
	@Column(columnDefinition = "LONGTEXT")
	private String responseJson;

	@Column(nullable = false, updatable = false)
	private Instant createdAt;

	@Column(nullable = false)
	private Instant updatedAt;

	@Column
	private Instant completedAt;
}
