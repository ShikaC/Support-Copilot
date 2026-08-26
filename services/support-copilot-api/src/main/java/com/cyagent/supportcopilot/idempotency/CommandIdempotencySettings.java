package com.cyagent.supportcopilot.idempotency;

import java.time.Duration;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class CommandIdempotencySettings {

	private final Duration leaseDuration;
	private final Duration waitTimeout;
	private final Duration pollInterval;

	public CommandIdempotencySettings(
		@Value("${support-copilot.idempotency.lease-duration:PT15S}") Duration leaseDuration,
		@Value("${support-copilot.idempotency.wait-timeout:PT10S}") Duration waitTimeout,
		@Value("${support-copilot.idempotency.poll-interval:PT0.05S}") Duration pollInterval
	) {
		this.leaseDuration = requirePositive(leaseDuration, "lease-duration");
		this.waitTimeout = requirePositive(waitTimeout, "wait-timeout");
		this.pollInterval = requirePositive(pollInterval, "poll-interval");
	}

	public Duration leaseDuration() {
		return leaseDuration;
	}

	public Duration waitTimeout() {
		return waitTimeout;
	}

	public Duration pollInterval() {
		return pollInterval;
	}

	public Duration heartbeatInterval() {
		return leaseDuration.dividedBy(3);
	}

	private Duration requirePositive(Duration duration, String name) {
		if (duration.isZero() || duration.isNegative()) {
			throw new IllegalStateException("Idempotency " + name + " must be positive.");
		}
		return duration;
	}
}
