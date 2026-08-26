package com.cyagent.supportcopilot.audit;

import org.springframework.context.annotation.Profile;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.cyagent.supportcopilot.audit.AuditEventDtos.AuditEventPage;

@RestController
@RequestMapping("/api/audit-events")
@Profile("!demo")
public class AuditEventController {

	private final AuditEventQueryService auditEventQueryService;

	public AuditEventController(AuditEventQueryService auditEventQueryService) {
		this.auditEventQueryService = auditEventQueryService;
	}

	@GetMapping
	AuditEventPage query(
		@RequestParam(required = false) String targetType,
		@RequestParam(required = false) String targetId,
		@RequestParam(required = false) String cursor,
		@RequestParam(required = false) String limit
	) {
		return auditEventQueryService.query(targetType, targetId, cursor, limit);
	}
}
