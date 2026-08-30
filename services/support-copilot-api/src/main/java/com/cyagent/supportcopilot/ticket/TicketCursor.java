package com.cyagent.supportcopilot.ticket;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;

public record TicketCursor(Instant createdAt, String id) {

	public TicketCursor {
		if (createdAt == null || id == null || id.isBlank() || id.length() > 255 || id.indexOf('\n') >= 0) {
			throw TicketQueryException.invalidCursor();
		}
	}

	public String encode() {
		var payload = createdAt + "\n" + id;
		return Base64.getUrlEncoder()
			.withoutPadding()
			.encodeToString(payload.getBytes(StandardCharsets.UTF_8));
	}

	public static TicketCursor decode(String encoded) {
		try {
			if (encoded == null || encoded.isBlank()) {
				throw TicketQueryException.invalidCursor();
			}
			var payload = new String(Base64.getUrlDecoder().decode(encoded), StandardCharsets.UTF_8);
			var fields = payload.split("\\n", -1);
			if (fields.length != 2) {
				throw TicketQueryException.invalidCursor();
			}
			return new TicketCursor(Instant.parse(fields[0]), fields[1]);
		} catch (TicketQueryException exception) {
			throw exception;
		} catch (RuntimeException exception) {
			throw TicketQueryException.invalidCursor();
		}
	}
}
