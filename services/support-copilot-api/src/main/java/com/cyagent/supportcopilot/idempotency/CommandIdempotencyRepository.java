package com.cyagent.supportcopilot.idempotency;

import java.time.Instant;
import java.util.Optional;

import jakarta.persistence.LockModeType;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface CommandIdempotencyRepository extends JpaRepository<CommandIdempotencyRecord, String> {

	@Lock(LockModeType.PESSIMISTIC_WRITE)
	Optional<CommandIdempotencyRecord> findForUpdateByIdempotencyKey(String idempotencyKey);

	@Modifying
	@Query("""
		update CommandIdempotencyRecord record
		set record.leaseExpiresAt = :leaseExpiresAt, record.updatedAt = :updatedAt
		where record.idempotencyKey = :idempotencyKey
		  and record.ownerToken = :ownerToken
		  and record.status = com.cyagent.supportcopilot.idempotency.CommandStatus.PENDING
		""")
	int renewLease(
		@Param("idempotencyKey") String idempotencyKey,
		@Param("ownerToken") String ownerToken,
		@Param("leaseExpiresAt") Instant leaseExpiresAt,
		@Param("updatedAt") Instant updatedAt
	);

	@Modifying(clearAutomatically = true, flushAutomatically = true)
	@Query("""
		update CommandIdempotencyRecord record
		set record.status = com.cyagent.supportcopilot.idempotency.CommandStatus.COMPLETED,
		    record.responseHttpStatus = :httpStatus,
		    record.responseJson = :responseJson,
		    record.ownerToken = null,
		    record.leaseExpiresAt = null,
		    record.updatedAt = :completedAt,
		    record.completedAt = :completedAt
		where record.idempotencyKey = :idempotencyKey
		  and record.ownerToken = :ownerToken
		  and record.status = com.cyagent.supportcopilot.idempotency.CommandStatus.PENDING
		""")
	int complete(
		@Param("idempotencyKey") String idempotencyKey,
		@Param("ownerToken") String ownerToken,
		@Param("httpStatus") int httpStatus,
		@Param("responseJson") String responseJson,
		@Param("completedAt") Instant completedAt
	);

	@Modifying(clearAutomatically = true, flushAutomatically = true)
	@Query("""
		update CommandIdempotencyRecord record
		set record.status = com.cyagent.supportcopilot.idempotency.CommandStatus.FAILED,
		    record.ownerToken = null,
		    record.leaseExpiresAt = null,
		    record.updatedAt = :failedAt
		where record.idempotencyKey = :idempotencyKey
		  and record.ownerToken = :ownerToken
		  and record.status = com.cyagent.supportcopilot.idempotency.CommandStatus.PENDING
		""")
	int fail(
		@Param("idempotencyKey") String idempotencyKey,
		@Param("ownerToken") String ownerToken,
		@Param("failedAt") Instant failedAt
	);
}
