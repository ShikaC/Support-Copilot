package com.cyagent.supportcopilot.idempotency;

public record CommandOwnership(String idempotencyKey, String ownerToken) {
}
