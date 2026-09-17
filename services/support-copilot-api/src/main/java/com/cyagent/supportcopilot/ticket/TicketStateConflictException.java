package com.cyagent.supportcopilot.ticket;

public class TicketStateConflictException extends RuntimeException {

	private final String ticketId;
	private final String currentStatus;
	private final String requestedStatus;

	public TicketStateConflictException(String ticketId, String currentStatus) {
		super("当前工单状态不允许此操作。", null);
		this.ticketId = ticketId;
		this.currentStatus = currentStatus;
		this.requestedStatus = null;
	}

	public TicketStateConflictException(String ticketId, String currentStatus, String requestedStatus) {
		super("当前工单状态不允许目标状态转换。", null);
		this.ticketId = ticketId;
		this.currentStatus = currentStatus;
		this.requestedStatus = requestedStatus;
	}

	public String getTicketId() {
		return ticketId;
	}

	public String getCurrentStatus() {
		return currentStatus;
	}

	public String getRequestedStatus() {
		return requestedStatus;
	}
}
