package com.cyagent.supportcopilot.config;

import java.io.IOException;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.http.MediaType;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.stereotype.Component;

import tools.jackson.databind.ObjectMapper;

import com.cyagent.supportcopilot.common.TraceId;

@Component
public class SecurityErrorHandlers {

	private final ObjectMapper objectMapper;

	public SecurityErrorHandlers(ObjectMapper objectMapper) {
		this.objectMapper = objectMapper;
	}

	AuthenticationEntryPoint authenticationEntryPoint() {
		return (request, response, exception) -> write(
			request,
			response,
			HttpServletResponse.SC_UNAUTHORIZED,
			"AUTHENTICATION_REQUIRED",
			"Authentication is required."
		);
	}

	AccessDeniedHandler accessDeniedHandler() {
		return (request, response, exception) -> write(
			request,
			response,
			HttpServletResponse.SC_FORBIDDEN,
			"ACCESS_DENIED",
			"The authenticated user does not have the required role."
		);
	}

	private void write(
		HttpServletRequest request,
		HttpServletResponse response,
		int status,
		String code,
		String message
	) throws IOException {
		var traceId = TraceId.from(request);
		request.setAttribute(TraceId.REQUEST_ATTRIBUTE, traceId);
		response.setStatus(status);
		response.setHeader(TraceId.HEADER_NAME, traceId);
		response.setContentType(MediaType.APPLICATION_JSON_VALUE);
		objectMapper.writeValue(response.getOutputStream(), new SecurityError(code, message, traceId));
	}

	private record SecurityError(String code, String message, String traceId) {
	}
}
