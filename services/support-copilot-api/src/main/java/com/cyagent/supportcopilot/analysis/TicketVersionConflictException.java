package com.cyagent.supportcopilot.analysis;

// 表示分析输入版本已经过期，不能把旧结果写回当前工单。
public class TicketVersionConflictException extends RuntimeException {

	private final String ticketId;
	private final long expectedVersion;
	private final Long currentVersion;

	public TicketVersionConflictException(String ticketId, long expectedVersion, long currentVersion) {
		this(ticketId, expectedVersion, currentVersion, null);
	}

	public TicketVersionConflictException(
		String ticketId,
		long expectedVersion,
		Long currentVersion,
		Throwable cause
	) {
		super("工单已被其他操作更新，本次操作基于旧版本，未保存。", cause);
		this.ticketId = ticketId;
		this.expectedVersion = expectedVersion;
		this.currentVersion = currentVersion;
	}

	public String getTicketId() {
		return ticketId;
	}

	public long getExpectedVersion() {
		return expectedVersion;
	}

	public Long getCurrentVersion() {
		return currentVersion;
	}
}
