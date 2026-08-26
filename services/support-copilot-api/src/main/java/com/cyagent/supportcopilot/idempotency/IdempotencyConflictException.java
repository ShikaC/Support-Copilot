package com.cyagent.supportcopilot.idempotency;

public class IdempotencyConflictException extends RuntimeException {

	public IdempotencyConflictException() {
		super("Idempotency-Key is already bound to a different command request.");
	}
}
