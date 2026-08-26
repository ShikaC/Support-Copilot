package com.cyagent.supportcopilot.audit;

import java.util.List;

public interface AuditEventRepository {

	void insert(AuditEvent event);

	List<AuditEvent> query(AuditEventQuery query);
}
