package com.cyagent.supportcopilot.analysis;

final class AiTransientFailureException extends AiServiceCallException {

	private final String outcome;

	AiTransientFailureException(FallbackReason fallbackReason, String outcome, Throwable cause) {
		super(fallbackReason, cause);
		this.outcome = outcome;
	}

	String outcome() {
		return outcome;
	}
}
