package com.cyagent.supportcopilot.common;

import java.time.Instant;
import java.util.Map;

import jakarta.persistence.EntityNotFoundException;
import jakarta.servlet.http.HttpServletRequest;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.BindException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class ApiExceptionHandler {

	@ExceptionHandler(EntityNotFoundException.class)
	ResponseEntity<ApiError> handleNotFound(EntityNotFoundException exception, HttpServletRequest request) {
		return ResponseEntity.status(HttpStatus.NOT_FOUND)
			.body(error("RESOURCE_NOT_FOUND", exception.getMessage(), request));
	}

	@ExceptionHandler({MethodArgumentNotValidException.class, BindException.class, IllegalArgumentException.class})
	ResponseEntity<ApiError> handleBadRequest(Exception exception, HttpServletRequest request) {
		return ResponseEntity.badRequest()
			.body(error("INVALID_REQUEST", "请求参数不符合业务约束。", request));
	}

	private ApiError error(String code, String message, HttpServletRequest request) {
		return new ApiError(code, message, request.getHeader("X-Trace-Id"), Instant.now(), Map.of());
	}

	public record ApiError(
		String code,
		String message,
		String traceId,
		Instant timestamp,
		Map<String, Object> details
	) {
	}
}
