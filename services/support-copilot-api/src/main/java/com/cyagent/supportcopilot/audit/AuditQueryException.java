package com.cyagent.supportcopilot.audit;

public class AuditQueryException extends IllegalArgumentException {

	public AuditQueryException(String message) {
		super(message);
	}

	public AuditQueryException(String message, Throwable cause) {
		super(message, cause);
	}
}
