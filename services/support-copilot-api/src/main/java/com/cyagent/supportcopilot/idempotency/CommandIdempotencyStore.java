package com.cyagent.supportcopilot.idempotency;

import java.time.Clock;
import java.time.Instant;
import java.util.UUID;

import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Component;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;

@Component
public class CommandIdempotencyStore {

	private final CommandIdempotencyRepository repository;
	private final CommandIdempotencySettings settings;
	private final Clock clock;
	private final TransactionTemplate requiresNew;

	public CommandIdempotencyStore(
		CommandIdempotencyRepository repository,
		CommandIdempotencySettings settings,
		PlatformTransactionManager transactionManager
	) {
		this.repository = repository;
		this.settings = settings;
		this.clock = Clock.systemUTC();
		this.requiresNew = new TransactionTemplate(transactionManager);
		this.requiresNew.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
	}

	public CommandResolution resolve(CommandRequest request) {
		try {
			return requiresNew.execute(status -> resolveInTransaction(request));
		} catch (DataIntegrityViolationException exception) {
			return requiresNew.execute(status -> resolveInTransaction(request));
		}
	}

	public boolean renew(CommandOwnership ownership) {
		return Boolean.TRUE.equals(requiresNew.execute(status -> {
			var now = clock.instant();
			return repository.renewLease(
				ownership.idempotencyKey(),
				ownership.ownerToken(),
				now.plus(settings.leaseDuration()),
				now
			) == 1;
		}));
	}

	public void fail(CommandOwnership ownership) {
		requiresNew.executeWithoutResult(status -> repository.fail(
			ownership.idempotencyKey(),
			ownership.ownerToken(),
			clock.instant()
		));
	}

	private CommandResolution resolveInTransaction(CommandRequest request) {
		var existing = repository.findForUpdateByIdempotencyKey(request.key().value());
		if (existing.isEmpty()) {
			return create(request);
		}

		var record = existing.get();
		if (!record.getRequestFingerprint().equals(request.requestFingerprint())
			|| record.getCommandType() != request.commandType()
			|| !record.getRouteScope().equals(request.routeScope())) {
			throw new IdempotencyConflictException();
		}
		if (record.getStatus() == CommandStatus.COMPLETED) {
			return new CommandResolution.Replay(record.getResponseHttpStatus(), record.getResponseJson());
		}

		var now = clock.instant();
		if (record.getStatus() == CommandStatus.FAILED || !record.getLeaseExpiresAt().isAfter(now)) {
			return claim(record, now);
		}
		return new CommandResolution.Pending();
	}

	private CommandResolution create(CommandRequest request) {
		var now = clock.instant();
		var ownerToken = UUID.randomUUID().toString();
		var record = new CommandIdempotencyRecord();
		record.setId("command-" + UUID.randomUUID());
		record.setIdempotencyKey(request.key().value());
		record.setRequestFingerprint(request.requestFingerprint());
		record.setCommandType(request.commandType());
		record.setRouteScope(request.routeScope());
		record.setStatus(CommandStatus.PENDING);
		record.setOwnerToken(ownerToken);
		record.setLeaseExpiresAt(now.plus(settings.leaseDuration()));
		record.setCreatedAt(now);
		record.setUpdatedAt(now);
		repository.saveAndFlush(record);
		return new CommandResolution.Owned(new CommandOwnership(request.key().value(), ownerToken));
	}

	private CommandResolution claim(CommandIdempotencyRecord record, Instant now) {
		var ownerToken = UUID.randomUUID().toString();
		record.setStatus(CommandStatus.PENDING);
		record.setOwnerToken(ownerToken);
		record.setLeaseExpiresAt(now.plus(settings.leaseDuration()));
		record.setResponseHttpStatus(null);
		record.setResponseJson(null);
		record.setCompletedAt(null);
		record.setUpdatedAt(now);
		repository.saveAndFlush(record);
		return new CommandResolution.Owned(new CommandOwnership(record.getIdempotencyKey(), ownerToken));
	}
}
