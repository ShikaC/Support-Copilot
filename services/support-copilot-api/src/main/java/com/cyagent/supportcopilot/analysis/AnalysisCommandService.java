package com.cyagent.supportcopilot.analysis;

import org.springframework.stereotype.Service;

import com.cyagent.supportcopilot.idempotency.CommandIdempotencyCoordinator;
import com.cyagent.supportcopilot.idempotency.CommandRequestFactory;
import com.cyagent.supportcopilot.idempotency.IdempotencyKey;

@Service
public class AnalysisCommandService {

	private final AnalysisService analysisService;
	private final CommandIdempotencyCoordinator idempotencyCoordinator;
	private final CommandRequestFactory commandRequestFactory;

	public AnalysisCommandService(
		AnalysisService analysisService,
		CommandIdempotencyCoordinator idempotencyCoordinator,
		CommandRequestFactory commandRequestFactory
	) {
		this.analysisService = analysisService;
		this.idempotencyCoordinator = idempotencyCoordinator;
		this.commandRequestFactory = commandRequestFactory;
	}

	public AnalysisResponse analyze(String ticketId, IdempotencyKey key) {
		var request = commandRequestFactory.analysis(key, ticketId);
		return idempotencyCoordinator.execute(
			request,
			AnalysisResponse.class,
			ownership -> analysisService.analyzeOwned(ticketId, ownership)
		);
	}
}
