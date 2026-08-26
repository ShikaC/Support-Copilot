package com.cyagent.supportcopilot.idempotency;

import java.util.regex.Pattern;

public record IdempotencyKey(String value) {

	private static final int MIN_LENGTH = 16;
	private static final int MAX_LENGTH = 128;
	private static final Pattern ALLOWED = Pattern.compile("[A-Za-z0-9][A-Za-z0-9._:-]*");

	public static IdempotencyKey parse(String rawValue) {
		if (rawValue == null || rawValue.isBlank()) {
			throw new IdempotencyKeyException(
				"IDEMPOTENCY_KEY_REQUIRED",
				"Idempotency-Key header is required."
			);
		}
		if (rawValue.length() < MIN_LENGTH
			|| rawValue.length() > MAX_LENGTH
			|| !ALLOWED.matcher(rawValue).matches()) {
			throw new IdempotencyKeyException(
				"INVALID_IDEMPOTENCY_KEY",
				"Idempotency-Key must be 16-128 ASCII letters, digits, '.', '_', ':', or '-'."
			);
		}
		return new IdempotencyKey(rawValue);
	}
}
