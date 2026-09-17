package com.cyagent.supportcopilot.ticket;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class TicketQueueCursorTests {
	@Test
	void bindsNormalizedFiltersRegardlessOfCaseOrderAndWhitespace() {
		var query = TicketQueueQuery.parse(" NEW,IN_PROGRESS ", " high,urgent ", null, " LOGIN ", " Agent ", "sla");
		var equivalent = TicketQueueQuery.parse("in_progress,new", "URGENT,HIGH", "", "login", "Agent", "SLA");
		var cursor = new TicketQueueCursor(Instant.parse("2026-01-01T00:00:00Z"),
			Instant.parse("2026-01-02T00:00:00Z"), "HIGH", "ticket-stable");
		assertThat(TicketQueueCursor.decode(cursor.encode(query), equivalent)).isEqualTo(cursor);
	}

	@Test
	void rejectsOversizedAndMalformedCursorWithoutInterpretingItAsAFirstPage() {
		var query = TicketQueueQuery.parse(null, null, null, null, null, null);
		for (var cursor : new String[] {"?bad", "x".repeat(2049), ""}) {
			assertThatThrownBy(() -> TicketQueueCursor.decode(cursor, query))
				.isInstanceOf(TicketQueryException.class);
		}
	}
}
