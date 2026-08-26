package com.cyagent.supportcopilot.analysis;

public class AiServiceRequestException extends IllegalStateException {

	public AiServiceRequestException(int statusCode, Throwable cause) {
		super("AI service rejected the internal request with HTTP " + statusCode + ".", cause);
	}
}
