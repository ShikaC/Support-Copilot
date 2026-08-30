package com.cyagent.supportcopilot.ticket;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;

import org.junit.jupiter.api.Test;

class TicketCursorTests {

	@Test
	void roundTripsTheStableSortKeyWithoutExposingItsWireFormat() {
		var cursor = new TicketCursor(Instant.parse("2026-07-28T07:31:00Z"), "ticket-10042");

		assertThat(TicketCursor.decode(cursor.encode())).isEqualTo(cursor);
	}

	@Test
	void rejectsMalformedAndAmbiguousCursors() {
		assertThatThrownBy(() -> TicketCursor.decode("not-a-cursor"))
			.isInstanceOf(TicketQueryException.class)
			.hasMessage("工单游标无效。");
	}
}
