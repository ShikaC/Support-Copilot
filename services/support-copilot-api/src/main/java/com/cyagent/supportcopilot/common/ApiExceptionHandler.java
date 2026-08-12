package com.cyagent.supportcopilot.common;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

import jakarta.persistence.EntityNotFoundException;
import jakarta.servlet.http.HttpServletRequest;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.BindException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import com.cyagent.supportcopilot.analysis.TicketVersionConflictException;
import com.cyagent.supportcopilot.ticket.TicketStateConflictException;

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

	// 将版本冲突转换为稳定的业务错误，让 React 能区分普通请求失败。
	@ExceptionHandler(TicketVersionConflictException.class)
	ResponseEntity<ApiError> handleVersionConflict(
		TicketVersionConflictException exception,
		HttpServletRequest request
	) {
		var details = new LinkedHashMap<String, Object>();
		details.put("ticketId", exception.getTicketId());
		details.put("expectedVersion", exception.getExpectedVersion());
		if (exception.getCurrentVersion() != null) {
			details.put("currentVersion", exception.getCurrentVersion());
		}
		return ResponseEntity.status(HttpStatus.CONFLICT)
			.body(new ApiError(
				"VERSION_CONFLICT",
				exception.getMessage(),
				request.getHeader("X-Trace-Id"),
				Instant.now(),
				details
			));
	}

	@ExceptionHandler(TicketStateConflictException.class)
	ResponseEntity<ApiError> handleTicketStateConflict(
		TicketStateConflictException exception,
		HttpServletRequest request
	) {
		var details = new LinkedHashMap<String, Object>();
		details.put("ticketId", exception.getTicketId());
		details.put("currentStatus", exception.getCurrentStatus());
		return ResponseEntity.status(HttpStatus.CONFLICT)
			.body(new ApiError(
				"TICKET_STATE_CONFLICT",
				exception.getMessage(),
				request.getHeader("X-Trace-Id"),
				Instant.now(),
				details
			));
	}

	private ApiError error(String code, String message, HttpServletRequest request) {
		return new ApiError(code, message, request.getHeader("X-Trace-Id"), Instant.now(), Map.of());
	}

	public record ApiError(
		String code,
		String message,
		// 贯穿浏览器、Java 和 Python 的请求标识，便于用日志定位同一次请求。
		String traceId,
		Instant timestamp,
		Map<String, Object> details
	) {
	}
}
