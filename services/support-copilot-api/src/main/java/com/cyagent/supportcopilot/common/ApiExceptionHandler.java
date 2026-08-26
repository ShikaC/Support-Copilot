package com.cyagent.supportcopilot.common;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

import jakarta.persistence.EntityNotFoundException;
import jakarta.servlet.http.HttpServletRequest;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.BindException;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import com.cyagent.supportcopilot.analysis.TicketVersionConflictException;
import com.cyagent.supportcopilot.analysis.review.StaleAnalysisReviewException;
import com.cyagent.supportcopilot.audit.AuditQueryException;
import com.cyagent.supportcopilot.ticket.Ticket;
import com.cyagent.supportcopilot.ticket.TicketRepository;
import com.cyagent.supportcopilot.ticket.TicketStateConflictException;
import com.cyagent.supportcopilot.idempotency.IdempotencyConflictException;
import com.cyagent.supportcopilot.idempotency.IdempotencyInProgressException;
import com.cyagent.supportcopilot.idempotency.IdempotencyKeyException;

@RestControllerAdvice
public class ApiExceptionHandler {
	private final TicketRepository ticketRepository;

	public ApiExceptionHandler(TicketRepository ticketRepository) {
		this.ticketRepository = ticketRepository;
	}

	@ExceptionHandler(IdempotencyKeyException.class)
	ResponseEntity<ApiError> handleIdempotencyKey(
		IdempotencyKeyException exception,
		HttpServletRequest request
	) {
		return ResponseEntity.badRequest().body(error(exception.getCode(), exception.getMessage(), request));
	}

	@ExceptionHandler(IdempotencyConflictException.class)
	ResponseEntity<ApiError> handleIdempotencyConflict(
		IdempotencyConflictException exception,
		HttpServletRequest request
	) {
		return ResponseEntity.status(HttpStatus.CONFLICT)
			.body(error("IDEMPOTENCY_KEY_CONFLICT", exception.getMessage(), request));
	}

	@ExceptionHandler(IdempotencyInProgressException.class)
	ResponseEntity<ApiError> handleIdempotencyInProgress(
		IdempotencyInProgressException exception,
		HttpServletRequest request
	) {
		return ResponseEntity.status(HttpStatus.CONFLICT)
			.body(error("IDEMPOTENCY_REQUEST_IN_PROGRESS", exception.getMessage(), request));
	}

	@ExceptionHandler(AuditQueryException.class)
	ResponseEntity<ApiError> handleAuditQuery(AuditQueryException exception, HttpServletRequest request) {
		return ResponseEntity.badRequest()
			.body(error("INVALID_AUDIT_QUERY", "审计查询参数不符合约束。", request));
	}

	@ExceptionHandler(EntityNotFoundException.class)
	ResponseEntity<ApiError> handleNotFound(EntityNotFoundException exception, HttpServletRequest request) {
		return ResponseEntity.status(HttpStatus.NOT_FOUND)
			.body(error("RESOURCE_NOT_FOUND", exception.getMessage(), request));
	}

	@ExceptionHandler({
		MethodArgumentNotValidException.class,
		BindException.class,
		HttpMessageNotReadableException.class,
		IllegalArgumentException.class
	})
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
		details.put("currentVersion", currentVersion(exception));
		return ResponseEntity.status(HttpStatus.CONFLICT)
			.body(new ApiError(
				"VERSION_CONFLICT",
				exception.getMessage(),
				TraceId.from(request),
				Instant.now(),
				details
			));
	}

	private Long currentVersion(TicketVersionConflictException exception) {
		if (exception.getCurrentVersion() != null) {
			return exception.getCurrentVersion();
		}
		return ticketRepository.findById(exception.getTicketId())
			.map(Ticket::getVersion)
			.orElse(null);
	}

	@ExceptionHandler(TicketStateConflictException.class)
	ResponseEntity<ApiError> handleTicketStateConflict(
		TicketStateConflictException exception,
		HttpServletRequest request
	) {
		var details = new LinkedHashMap<String, Object>();
		details.put("ticketId", exception.getTicketId());
		details.put("currentStatus", exception.getCurrentStatus());
		if (exception.getRequestedStatus() != null) {
			details.put("requestedStatus", exception.getRequestedStatus());
		}
		return ResponseEntity.status(HttpStatus.CONFLICT)
			.body(new ApiError(
				"TICKET_STATE_CONFLICT",
				exception.getMessage(),
				TraceId.from(request),
				Instant.now(),
				details
			));
	}

	@ExceptionHandler(StaleAnalysisReviewException.class)
	ResponseEntity<ApiError> handleStaleAnalysisReview(
		StaleAnalysisReviewException exception,
		HttpServletRequest request
	) {
		var details = new LinkedHashMap<String, Object>();
		details.put("ticketId", exception.getTicketId());
		details.put("analysisId", exception.getAnalysisId());
		details.put("latestAnalysisId", exception.getLatestAnalysisId());
		details.put("expectedTicketVersion", exception.getExpectedTicketVersion());
		details.put("currentTicketVersion", exception.getCurrentTicketVersion());
		return ResponseEntity.status(HttpStatus.CONFLICT)
			.body(new ApiError(
				"ANALYSIS_REVIEW_STALE",
				exception.getMessage(),
				TraceId.from(request),
				Instant.now(),
				details
			));
	}

	private ApiError error(String code, String message, HttpServletRequest request) {
		return new ApiError(code, message, TraceId.from(request), Instant.now(), Map.of());
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
