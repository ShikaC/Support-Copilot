package com.cyagent.supportcopilot.analysis;

public class AiServiceContractException extends IllegalStateException {

	public AiServiceContractException(String message) {
		super(message);
	}

	public AiServiceContractException(String message, Throwable cause) {
		super(message, cause);
	}
}
