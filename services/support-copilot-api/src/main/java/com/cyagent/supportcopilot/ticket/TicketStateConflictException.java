package com.cyagent.supportcopilot.ticket;

public class TicketStateConflictException extends RuntimeException {

	private final String ticketId;
	private final String currentStatus;

	public TicketStateConflictException(String ticketId, String currentStatus) {
		super("当前工单状态不允许取消负责人。", null);
		this.ticketId = ticketId;
		this.currentStatus = currentStatus;
	}

	public String getTicketId() {
		return ticketId;
	}

	public String getCurrentStatus() {
		return currentStatus;
	}
}
