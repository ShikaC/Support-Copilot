package com.cyagent.supportcopilot.analysis;

import java.net.URI;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties(prefix = "ai.service")
public record AiServiceProperties(
	@NotBlank String baseUrl,
	@Min(50) @Max(120_000) long timeoutMs,
	@Min(1) @Max(3) int retryMaxAttempts,
	@Min(0) @Max(5_000) long retryWaitMs,
	@Min(2) @Max(100) int circuitSlidingWindowSize,
	@Min(2) @Max(100) int circuitMinimumCalls,
	@Min(1) @Max(100) float circuitFailureRateThreshold,
	@Min(100) @Max(300_000) long circuitOpenMs,
	@Min(1) @Max(100) int bulkheadMaxConcurrentCalls,
	@Min(0) @Max(1_000) long bulkheadMaxWaitMs
) {
	public AiServiceProperties {
		var uri = URI.create(baseUrl);
		if (!("http".equals(uri.getScheme()) || "https".equals(uri.getScheme())) || uri.getHost() == null) {
			throw new IllegalArgumentException("ai.service.base-url must be an absolute HTTP(S) URL");
		}
		if (circuitMinimumCalls > circuitSlidingWindowSize) {
			throw new IllegalArgumentException(
				"ai.service.circuit-minimum-calls must not exceed the sliding window"
			);
		}
	}
}
