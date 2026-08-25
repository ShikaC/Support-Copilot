package com.cyagent.supportcopilot.analysis;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.function.Supplier;

import org.springframework.stereotype.Component;

@Component
public class AnalysisSingleFlightCoordinator {

	private final ConcurrentMap<AnalysisKey, CompletableFuture<AnalysisResponse>> inFlight =
		new ConcurrentHashMap<>();

	public Result execute(
		String ticketId,
		long sourceTicketVersion,
		String policyVersion,
		Supplier<AnalysisResponse> operation
	) {
		var key = new AnalysisKey(ticketId, sourceTicketVersion, policyVersion);
		var candidate = new CompletableFuture<AnalysisResponse>();
		var existing = inFlight.putIfAbsent(key, candidate);
		if (existing != null) {
			return new Result(await(existing), true);
		}

		try {
			var response = operation.get();
			candidate.complete(response);
			return new Result(response, false);
		} catch (RuntimeException | Error exception) {
			candidate.completeExceptionally(exception);
			throw exception;
		} finally {
			inFlight.remove(key, candidate);
		}
	}

	private AnalysisResponse await(CompletableFuture<AnalysisResponse> execution) {
		try {
			return execution.join();
		} catch (CompletionException exception) {
			if (exception.getCause() instanceof RuntimeException runtimeException) {
				throw runtimeException;
			}
			if (exception.getCause() instanceof Error error) {
				throw error;
			}
			throw exception;
		}
	}

	public record Result(AnalysisResponse response, boolean joined) {
	}

	private record AnalysisKey(String ticketId, long sourceTicketVersion, String policyVersion) {
	}
}
