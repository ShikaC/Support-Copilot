package com.cyagent.supportcopilot.idempotency;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

class IdempotencyKeyTests {

	@Test
	void acceptsConservativeAsciiKeysAtBothLengthBoundaries() {
		assertThat(IdempotencyKey.parse("a".repeat(16)).value()).hasSize(16);
		assertThat(IdempotencyKey.parse("A0._:-" + "z".repeat(122)).value()).hasSize(128);
	}

	@Test
	void rejectsBlankShortLongWhitespaceAndNonAsciiKeys() {
		for (var value : new String[] { null, "", "   " }) {
			assertThatThrownBy(() -> IdempotencyKey.parse(value))
			.isInstanceOf(IdempotencyKeyException.class)
			.hasMessage("Idempotency-Key header is required.");
		}
		for (var value : new String[] { "short", "a".repeat(129), "contains whitespace", "幂等键不允许" }) {
			assertThatThrownBy(() -> IdempotencyKey.parse(value))
				.isInstanceOf(IdempotencyKeyException.class)
				.hasMessageContaining("16-128 ASCII");
		}
	}
}
