package com.cyagent.supportcopilot.idempotency;

public class IdempotencyInProgressException extends RuntimeException {

	public IdempotencyInProgressException() {
		super("The command identified by Idempotency-Key is still in progress.");
	}
}
