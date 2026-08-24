package com.cyagent.supportcopilot.common;

import java.util.UUID;
import java.util.regex.Pattern;

import jakarta.servlet.http.HttpServletRequest;

import org.slf4j.MDC;

public final class TraceId {

	public static final String HEADER_NAME = "X-Trace-Id";
	public static final String MDC_KEY = "traceId";
	public static final String REQUEST_ATTRIBUTE = TraceId.class.getName() + ".value";

	private static final Pattern SAFE_VALUE = Pattern.compile("[A-Za-z0-9][A-Za-z0-9._-]{0,79}");

	private TraceId() {
	}

	public static String resolve(String candidate) {
		return candidate != null && SAFE_VALUE.matcher(candidate).matches()
			? candidate
			: generated();
	}

	public static String currentOrCreate() {
		return resolve(MDC.get(MDC_KEY));
	}

	public static String from(HttpServletRequest request) {
		var attribute = request.getAttribute(REQUEST_ATTRIBUTE);
		return attribute instanceof String traceId
			? traceId
			: resolve(request.getHeader(HEADER_NAME));
	}

	private static String generated() {
		return "trace_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12);
	}
}
