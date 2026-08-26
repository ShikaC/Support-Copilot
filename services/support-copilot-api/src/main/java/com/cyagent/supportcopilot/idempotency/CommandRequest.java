package com.cyagent.supportcopilot.idempotency;

public record CommandRequest(
	IdempotencyKey key,
	CommandType commandType,
	String routeScope,
	String requestFingerprint
) {
}
