package com.cyagent.supportcopilot.idempotency;

import java.time.Clock;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.function.Function;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

import jakarta.annotation.PreDestroy;

import org.springframework.stereotype.Component;

@Component
public class CommandIdempotencyCoordinator {

	private final CommandIdempotencyStore store;
	private final CommandIdempotencySettings settings;
	private final ObjectMapper objectMapper;
	private final Clock clock = Clock.systemUTC();
	private final ScheduledExecutorService heartbeatExecutor = Executors.newScheduledThreadPool(2, runnable -> {
		var thread = new Thread(runnable, "command-idempotency-heartbeat");
		thread.setDaemon(true);
		return thread;
	});

	public CommandIdempotencyCoordinator(
		CommandIdempotencyStore store,
		CommandIdempotencySettings settings,
		ObjectMapper objectMapper
	) {
		this.store = store;
		this.settings = settings;
		this.objectMapper = objectMapper;
	}

	public <T> T execute(
		CommandRequest request,
		Class<T> responseType,
		Function<CommandOwnership, T> operation
	) {
		var deadline = clock.instant().plus(settings.waitTimeout());
		while (true) {
			var resolution = store.resolve(request);
			if (resolution instanceof CommandResolution.Owned owned) {
				return executeOwned(owned.ownership(), operation);
			}
			if (resolution instanceof CommandResolution.Replay replay) {
				return deserialize(replay.responseJson(), responseType);
			}
			if (!clock.instant().isBefore(deadline)) {
				throw new IdempotencyInProgressException();
			}
			pause();
		}
	}

	@PreDestroy
	void close() {
		heartbeatExecutor.shutdownNow();
	}

	private <T> T executeOwned(CommandOwnership ownership, Function<CommandOwnership, T> operation) {
		var heartbeatMillis = Math.max(1, settings.heartbeatInterval().toMillis());
		var heartbeat = heartbeatExecutor.scheduleWithFixedDelay(
			() -> store.renew(ownership),
			heartbeatMillis,
			heartbeatMillis,
			TimeUnit.MILLISECONDS
		);
		try {
			return operation.apply(ownership);
		} catch (RuntimeException | Error exception) {
			store.fail(ownership);
			throw exception;
		} finally {
			heartbeat.cancel(false);
		}
	}

	private <T> T deserialize(String responseJson, Class<T> responseType) {
		try {
			return objectMapper.readValue(responseJson, responseType);
		} catch (JacksonException exception) {
			throw new IllegalStateException("Unable to replay idempotent command response", exception);
		}
	}

	private void pause() {
		try {
			Thread.sleep(settings.pollInterval());
		} catch (InterruptedException exception) {
			Thread.currentThread().interrupt();
			throw new IdempotencyInProgressException();
		}
	}
}
