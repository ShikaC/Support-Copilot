package com.cyagent.supportcopilot.audit;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Arrays;
import java.util.Base64;
import java.util.List;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.cyagent.supportcopilot.audit.AuditEventDtos.AuditEventPage;
import com.cyagent.supportcopilot.audit.AuditEventDtos.AuditEventResponse;

@Service
public class AuditEventQueryService {

	private static final int DEFAULT_LIMIT = 50;
	private static final int MAX_LIMIT = 100;

	private final AuditEventRepository auditEventRepository;
	private final ObjectMapper objectMapper;

	public AuditEventQueryService(AuditEventRepository auditEventRepository, ObjectMapper objectMapper) {
		this.auditEventRepository = auditEventRepository;
		this.objectMapper = objectMapper;
	}

	@Transactional(readOnly = true)
	public AuditEventPage query(String targetType, String targetId, String cursor, String limit) {
		var parsedTargetType = parseTargetType(targetType);
		var parsedTargetId = parseTargetId(targetId);
		var parsedCursor = parseCursor(cursor);
		var parsedLimit = parseLimit(limit);
		var events = auditEventRepository.query(new AuditEventQuery(
			parsedTargetType,
			parsedTargetId,
			parsedCursor == null ? null : parsedCursor.createdAt(),
			parsedCursor == null ? null : parsedCursor.id(),
			parsedLimit + 1
		));
		var hasNext = events.size() > parsedLimit;
		var pageEvents = hasNext ? events.subList(0, parsedLimit) : events;
		var items = pageEvents.stream().map(this::toResponse).toList();
		var nextCursor = hasNext ? encodeCursor(pageEvents.getLast()) : null;
		return new AuditEventPage(items, nextCursor);
	}

	private AuditTargetType parseTargetType(String value) {
		if (value == null) {
			return null;
		}
		try {
			return AuditTargetType.valueOf(value);
		} catch (IllegalArgumentException exception) {
			throw new AuditQueryException("Audit target type is invalid.", exception);
		}
	}

	private String parseTargetId(String value) {
		if (value == null) {
			return null;
		}
		var normalized = value.trim();
		if (normalized.isEmpty() || normalized.length() > 255) {
			throw new AuditQueryException("Audit target id is invalid.");
		}
		return normalized;
	}

	private int parseLimit(String value) {
		if (value == null) {
			return DEFAULT_LIMIT;
		}
		try {
			var parsed = Integer.parseInt(value);
			if (parsed < 1 || parsed > MAX_LIMIT) {
				throw new AuditQueryException("Audit limit is outside the allowed range.");
			}
			return parsed;
		} catch (NumberFormatException exception) {
			throw new AuditQueryException("Audit limit is invalid.", exception);
		}
	}

	private Cursor parseCursor(String value) {
		if (value == null) {
			return null;
		}
		try {
			var decoded = Base64.getUrlDecoder().decode(value);
			var cursor = objectMapper.readValue(new String(decoded, StandardCharsets.UTF_8), Cursor.class);
			if (cursor.createdAt() == null || cursor.id() == null || cursor.id().isBlank()
				|| cursor.id().length() > 64) {
				throw new AuditQueryException("Audit cursor is invalid.");
			}
			return cursor;
		} catch (IllegalArgumentException | JacksonException exception) {
			if (exception instanceof AuditQueryException auditQueryException) {
				throw auditQueryException;
			}
			throw new AuditQueryException("Audit cursor is invalid.", exception);
		}
	}

	private String encodeCursor(AuditEvent event) {
		try {
			var json = objectMapper.writeValueAsBytes(new Cursor(event.getCreatedAt(), event.getId()));
			return Base64.getUrlEncoder().withoutPadding().encodeToString(json);
		} catch (JacksonException exception) {
			throw new IllegalStateException("Unable to encode audit cursor.", exception);
		}
	}

	private AuditEventResponse toResponse(AuditEvent event) {
		try {
			return new AuditEventResponse(
				event.getId(),
				event.getActorSubject(),
				event.getActorType(),
				List.copyOf(Arrays.asList(objectMapper.readValue(event.getActorRolesJson(), String[].class))),
				AuditAction.valueOf(event.getAction()),
				AuditTargetType.valueOf(event.getTargetType()),
				event.getTargetId(),
				event.getTargetVersion(),
				event.getTraceId(),
				event.getCreatedAt(),
				objectMapper.readTree(event.getMetadataJson())
			);
		} catch (JacksonException exception) {
			throw new IllegalStateException("Unable to read redacted audit data.", exception);
		}
	}

	private record Cursor(Instant createdAt, String id) {
	}
}
