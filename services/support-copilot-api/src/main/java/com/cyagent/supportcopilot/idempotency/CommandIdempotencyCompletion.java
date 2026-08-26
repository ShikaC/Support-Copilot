package com.cyagent.supportcopilot.idempotency;

import java.time.Clock;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Component
public class CommandIdempotencyCompletion {

	private final CommandIdempotencyRepository repository;
	private final ObjectMapper objectMapper;
	private final Clock clock = Clock.systemUTC();

	public CommandIdempotencyCompletion(
		CommandIdempotencyRepository repository,
		ObjectMapper objectMapper
	) {
		this.repository = repository;
		this.objectMapper = objectMapper;
	}

	@Transactional(propagation = Propagation.MANDATORY)
	public void complete(CommandOwnership ownership, int httpStatus, Object response) {
		var completed = repository.complete(
			ownership.idempotencyKey(),
			ownership.ownerToken(),
			httpStatus,
			serialize(response),
			clock.instant()
		);
		if (completed != 1) {
			throw new IllegalStateException("Idempotent command ownership was lost before completion.");
		}
	}

	private String serialize(Object response) {
		try {
			return objectMapper.writeValueAsString(response);
		} catch (JacksonException exception) {
			throw new IllegalStateException("Unable to persist idempotent command response", exception);
		}
	}
}
