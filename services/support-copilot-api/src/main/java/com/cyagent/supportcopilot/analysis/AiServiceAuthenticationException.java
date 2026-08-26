package com.cyagent.supportcopilot.analysis;

public class AiServiceAuthenticationException extends IllegalStateException {

	public AiServiceAuthenticationException(Throwable cause) {
		super("AI service rejected the configured internal service identity.", cause);
	}
}
