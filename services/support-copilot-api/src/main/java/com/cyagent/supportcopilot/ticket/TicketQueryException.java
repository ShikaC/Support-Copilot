package com.cyagent.supportcopilot.ticket;

public final class TicketQueryException extends IllegalArgumentException {

	private final String code;

	private TicketQueryException(String code, String message) {
		super(message);
		this.code = code;
	}

	public static TicketQueryException invalidCursor() {
		return new TicketQueryException("INVALID_TICKET_CURSOR", "工单游标无效。");
	}

	public static TicketQueryException invalidPageSize() {
		return new TicketQueryException("INVALID_TICKET_PAGE", "工单分页大小必须在 1 到 100 之间。");
	}

	public static TicketQueryException invalidFilter() {
		return new TicketQueryException("INVALID_TICKET_FILTER", "工单筛选参数无效。");
	}

	public String code() {
		return code;
	}
}
