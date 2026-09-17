package com.cyagent.supportcopilot.ticket;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.DateTimeException;
import java.util.Base64;

public record TicketQueueCursor(Instant createdAt, Instant slaDeadline, String priority, String id) {
	public static TicketQueueCursor from(Ticket ticket) {
		return new TicketQueueCursor(ticket.getCreatedAt(), ticket.getSlaDeadline(), ticket.getPriority(), ticket.getId());
	}

	public String encode(TicketQueueQuery query) {
		var payload = String.join("\n", "v2", query.fingerprint(), createdAt.toString(),
			slaDeadline.toString(), priority, id);
		return Base64.getUrlEncoder().withoutPadding().encodeToString(payload.getBytes(StandardCharsets.UTF_8));
	}

	public static TicketQueueCursor decode(String encoded, TicketQueueQuery query) {
		try {
			if (encoded.length() > 2048) throw TicketQueryException.invalidCursor();
			var fields = new String(Base64.getUrlDecoder().decode(encoded), StandardCharsets.UTF_8).split("\n", -1);
			if (fields.length != 6 || !fields[0].equals("v2") || !fields[1].equals(query.fingerprint())
				|| fields[5].isBlank() || fields[5].length() > 255) {
				throw TicketQueryException.invalidCursor();
			}
			return new TicketQueueCursor(Instant.parse(fields[2]), Instant.parse(fields[3]),
				TicketDomain.parsePriority(fields[4]).name(), fields[5]);
		} catch (IllegalArgumentException | DateTimeException exception) {
			throw TicketQueryException.invalidCursor();
		}
	}
}
