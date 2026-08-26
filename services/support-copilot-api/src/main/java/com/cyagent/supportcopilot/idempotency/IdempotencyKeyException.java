package com.cyagent.supportcopilot.idempotency;

public class IdempotencyKeyException extends RuntimeException {

	private final String code;

	public IdempotencyKeyException(String code, String message) {
		super(message);
		this.code = code;
	}

	public String getCode() {
		return code;
	}
}
