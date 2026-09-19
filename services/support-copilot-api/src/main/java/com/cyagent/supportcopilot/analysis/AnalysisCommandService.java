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
	private final AnalysisResponseAccessPolicy accessPolicy;

	public AnalysisCommandService(
		AnalysisService analysisService,
		CommandIdempotencyCoordinator idempotencyCoordinator,
		CommandRequestFactory commandRequestFactory,
		AnalysisResponseAccessPolicy accessPolicy
	) {
		this.analysisService = analysisService;
		this.idempotencyCoordinator = idempotencyCoordinator;
		this.commandRequestFactory = commandRequestFactory;
		this.accessPolicy = accessPolicy;
	}

	public AnalysisResponse analyze(String ticketId, IdempotencyKey key) {
		var request = commandRequestFactory.analysis(key, ticketId);
		return accessPolicy.requireReadable(idempotencyCoordinator.execute(
			request,
			AnalysisResponse.class,
			ownership -> analysisService.analyzeOwned(ticketId, ownership)
		));
	}
}
