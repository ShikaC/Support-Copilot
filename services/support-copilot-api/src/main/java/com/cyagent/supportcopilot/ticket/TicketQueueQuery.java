package com.cyagent.supportcopilot.ticket;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.Locale;
import java.util.Set;
import java.util.TreeSet;
import java.util.function.Function;

public record TicketQueueQuery(
	Set<String> statuses, Set<String> priorities, Set<String> categories,
	String keyword, String assignee, Sort sort
) {
	public enum Sort { NEWEST, SLA, PRIORITY }

	public TicketQueueQuery {
		statuses = Set.copyOf(statuses);
		priorities = Set.copyOf(priorities);
		categories = Set.copyOf(categories);
	}

	public static TicketQueueQuery parse(
		String status, String priority, String category, String keyword, String assignee, String sort
	) {
		try {
			var normalizedKeyword = keyword == null ? "" : keyword.trim().toLowerCase(Locale.ROOT);
			var normalizedAssignee = assignee == null ? "" : assignee.trim();
			if (normalizedKeyword.length() > 120 || normalizedAssignee.length() > 80) {
				throw TicketQueryException.invalidFilter();
			}
			return new TicketQueueQuery(
				values(status, value -> TicketDomain.parseStatus(value).name()),
				values(priority, value -> TicketDomain.parsePriority(value).name()),
				values(category, value -> TicketDomain.parseCategory(value).name()),
				normalizedKeyword,
				normalizedAssignee,
				sort == null || sort.isBlank() ? Sort.NEWEST : Sort.valueOf(sort.trim().toUpperCase(Locale.ROOT))
			);
		} catch (IllegalArgumentException exception) {
			throw TicketQueryException.invalidFilter();
		}
	}

	public String fingerprint() {
		var fields = new String[] {
			String.join(",", new TreeSet<>(statuses)), String.join(",", new TreeSet<>(priorities)),
			String.join(",", new TreeSet<>(categories)), keyword, assignee, sort.name()
		};
		var canonical = new StringBuilder();
		for (var field : fields) {
			canonical.append(field.length()).append(':').append(field);
		}
		try {
			return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
				.digest(canonical.toString().getBytes(StandardCharsets.UTF_8)));
		} catch (NoSuchAlgorithmException exception) {
			throw new IllegalStateException("JVM does not provide SHA-256", exception);
		}
	}

	private static Set<String> values(String raw, Function<String, String> parser) {
		if (raw == null || raw.isBlank()) return Set.of();
		var values = new TreeSet<String>();
		Arrays.stream(raw.split(",", -1)).map(String::trim).filter(value -> !value.isBlank())
			.map(value -> parser.apply(value.toUpperCase(Locale.ROOT))).forEach(values::add);
		if (values.isEmpty()) throw TicketQueryException.invalidFilter();
		return values;
	}
}
