package com.cyagent.supportcopilot.ticket;

import java.util.Map;
import java.util.Set;

public final class TicketDomain {

	private static final Map<Status, Set<Status>> MANUAL_TRANSITIONS = Map.of(
		Status.NEW, Set.of(Status.IN_PROGRESS),
		Status.READY_FOR_REVIEW, Set.of(Status.IN_PROGRESS),
		Status.READY_FOR_MANUAL_REVIEW, Set.of(Status.IN_PROGRESS),
		Status.NEEDS_ESCALATION, Set.of(Status.IN_PROGRESS),
		Status.IN_PROGRESS, Set.of(Status.WAITING_CUSTOMER, Status.RESOLVED),
		Status.WAITING_CUSTOMER, Set.of(Status.IN_PROGRESS),
		Status.RESOLVED, Set.of(Status.CLOSED),
		Status.CLOSED, Set.of()
	);

	private TicketDomain() {
	}

	public enum Status {
		NEW,
		READY_FOR_REVIEW,
		READY_FOR_MANUAL_REVIEW,
		NEEDS_ESCALATION,
		IN_PROGRESS,
		WAITING_CUSTOMER,
		RESOLVED,
		CLOSED
	}

	public enum Priority {
		LOW,
		MEDIUM,
		HIGH,
		URGENT
	}

	public enum Channel {
		EMAIL,
		CHAT,
		WEB_FORM,
		PHONE
	}

	public enum CustomerTier {
		STANDARD,
		PREMIUM,
		ENTERPRISE
	}

	public enum Category {
		UNCLASSIFIED,
		GENERAL,
		BILLING,
		ACCOUNT_ACCESS,
		INVOICE,
		DATA_EXPORT,
		SUBSCRIPTION,
		PRIVACY,
		SECURITY,
		LEGAL,
		TECHNICAL,
		DATA_RECOVERY
	}

	public enum AnalysisStatus {
		SUCCEEDED,
		FALLBACK
	}

	public static void requireManualTransition(String ticketId, String currentValue, Status requested) {
		var current = parseStatus(currentValue);
		if (current == requested) {
			return;
		}
		if (!MANUAL_TRANSITIONS.get(current).contains(requested)) {
			throw new TicketStateConflictException(ticketId, current.name(), requested.name());
		}
	}

	public static Status analysisResultStatus(String ticketId, String currentValue, boolean escalationRequired) {
		var current = parseStatus(currentValue);
		if (current == Status.RESOLVED || current == Status.CLOSED) {
			throw new TicketStateConflictException(ticketId, current.name());
		}
		return escalationRequired ? Status.NEEDS_ESCALATION : Status.READY_FOR_REVIEW;
	}

	public static Status parseStatus(String value) {
		return parse(Status.class, value);
	}

	public static Priority parsePriority(String value) {
		return parse(Priority.class, value);
	}

	public static Category parseCategory(String value) {
		return parse(Category.class, value);
	}

	public static AnalysisStatus parseAnalysisStatus(String value) {
		return parse(AnalysisStatus.class, value);
	}

	private static <T extends Enum<T>> T parse(Class<T> type, String value) {
		if (value == null) {
			throw new IllegalArgumentException(type.getSimpleName() + " is required");
		}
		try {
			return Enum.valueOf(type, value);
		} catch (IllegalArgumentException exception) {
			throw new IllegalArgumentException("Unsupported " + type.getSimpleName() + ": " + value, exception);
		}
	}
}
