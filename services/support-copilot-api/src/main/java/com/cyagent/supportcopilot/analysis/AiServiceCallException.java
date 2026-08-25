package com.cyagent.supportcopilot.analysis;

public class AiServiceCallException extends RuntimeException {

	private final FallbackReason fallbackReason;

	public AiServiceCallException(FallbackReason fallbackReason) {
		super("AI service call failed: " + fallbackReason.value());
		this.fallbackReason = fallbackReason;
	}

	public AiServiceCallException(FallbackReason fallbackReason, Throwable cause) {
		super("AI service call failed: " + fallbackReason.value(), cause);
		this.fallbackReason = fallbackReason;
	}

	public FallbackReason getFallbackReason() {
		return fallbackReason;
	}
}
