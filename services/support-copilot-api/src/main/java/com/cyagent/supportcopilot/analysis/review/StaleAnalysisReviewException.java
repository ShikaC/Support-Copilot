package com.cyagent.supportcopilot.analysis.review;

import lombok.Getter;

@Getter
public class StaleAnalysisReviewException extends RuntimeException {

	private final String ticketId;
	private final String analysisId;
	private final String latestAnalysisId;
	private final Long expectedTicketVersion;
	private final Long currentTicketVersion;

	public StaleAnalysisReviewException(
		String ticketId,
		String analysisId,
		String latestAnalysisId,
		Long expectedTicketVersion,
		Long currentTicketVersion
	) {
		super("工单或分析结果已经变化，请刷新后重新审核。");
		this.ticketId = ticketId;
		this.analysisId = analysisId;
		this.latestAnalysisId = latestAnalysisId;
		this.expectedTicketVersion = expectedTicketVersion;
		this.currentTicketVersion = currentTicketVersion;
	}
}
