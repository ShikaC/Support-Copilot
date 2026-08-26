package com.cyagent.supportcopilot.analysis;

import java.net.http.HttpClient;
import java.net.http.HttpTimeoutException;
import java.time.Duration;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.function.Supplier;

import jakarta.annotation.PreDestroy;
import io.github.resilience4j.bulkhead.Bulkhead;
import io.github.resilience4j.bulkhead.BulkheadConfig;
import io.github.resilience4j.bulkhead.BulkheadFullException;
import io.github.resilience4j.circuitbreaker.CallNotPermittedException;
import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerConfig;
import io.github.resilience4j.retry.Retry;
import io.github.resilience4j.retry.RetryConfig;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

import com.cyagent.supportcopilot.common.TraceId;
import com.cyagent.supportcopilot.ticket.Ticket;

@Component
public class AiServiceClient {

	private static final Logger log = LoggerFactory.getLogger(AiServiceClient.class);
	private static final String METRIC_PREFIX = "support.copilot.ai.boundary.";

	private final RestClient restClient;
	private final String internalServiceToken;
	private final MeterRegistry meterRegistry;
	private final Retry retry;
	private final CircuitBreaker circuitBreaker;
	private final Bulkhead bulkhead;
	private final long overallTimeoutMs;
	private final ExecutorService deadlineExecutor = Executors.newVirtualThreadPerTaskExecutor();
	private final ThreadLocal<String> retryTraceId = new ThreadLocal<>();

	public AiServiceClient(
		AiServiceProperties properties,
		@Value("${support-copilot.security.internal-service-token}") String internalServiceToken,
		MeterRegistry meterRegistry
	) {
		if (internalServiceToken.isBlank()) {
			throw new IllegalStateException(
				"SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN must be configured with a non-blank value."
			);
		}
		this.internalServiceToken = internalServiceToken;
		this.meterRegistry = meterRegistry;
		this.overallTimeoutMs = properties.timeoutMs();
		var timeout = Duration.ofMillis(properties.timeoutMs() + 1_000);
		var httpClient = HttpClient.newBuilder()
			.version(HttpClient.Version.HTTP_1_1)
			.connectTimeout(timeout)
			.build();
		var requestFactory = new JdkClientHttpRequestFactory(httpClient);
		requestFactory.setReadTimeout(timeout);
		this.restClient = RestClient.builder()
			.baseUrl(properties.baseUrl())
			.requestFactory(requestFactory)
			.build();

		this.retry = Retry.of("ai", RetryConfig.custom()
			.maxAttempts(properties.retryMaxAttempts())
			.waitDuration(Duration.ofMillis(properties.retryWaitMs()))
			.retryExceptions(AiTransientFailureException.class)
			.build());
		this.retry.getEventPublisher().onRetry(event -> log.atWarn()
			.addKeyValue("trace_id", retryTraceId.get())
			.addKeyValue("attempt", event.getNumberOfRetryAttempts() + 1)
			.addKeyValue("outcome", transientOutcome(event.getLastThrowable()))
			.log("ai.boundary.retry"));

		this.circuitBreaker = CircuitBreaker.of("ai", CircuitBreakerConfig.custom()
			.slidingWindowType(CircuitBreakerConfig.SlidingWindowType.COUNT_BASED)
			.slidingWindowSize(properties.circuitSlidingWindowSize())
			.minimumNumberOfCalls(properties.circuitMinimumCalls())
			.failureRateThreshold(properties.circuitFailureRateThreshold())
			.waitDurationInOpenState(Duration.ofMillis(properties.circuitOpenMs()))
			.recordException(exception -> exception instanceof AiTransientFailureException)
			.build());
		this.bulkhead = Bulkhead.of("ai", BulkheadConfig.custom()
			.maxConcurrentCalls(properties.bulkheadMaxConcurrentCalls())
			.maxWaitDuration(Duration.ofMillis(properties.bulkheadMaxWaitMs()))
			.build());
	}

	public AnalysisResponse analyze(Ticket ticket, String traceId) {
		var timer = Timer.start(meterRegistry);
		var future = deadlineExecutor.submit(() -> executeProtected(ticket, traceId));
		try {
			var response = future.get(overallTimeoutMs, TimeUnit.MILLISECONDS);
			recordOutcome(timer, "success", providerMode(response));
			return response;
		} catch (TimeoutException exception) {
			future.cancel(true);
			meterRegistry.counter(METRIC_PREFIX + "timeouts", "stage", "java_deadline").increment();
			log.atWarn().addKeyValue("trace_id", traceId).log("ai.boundary.deadline_exceeded");
			var failure = new AiServiceCallException(FallbackReason.AI_SERVICE_TIMEOUT, exception);
			recordFallback(timer, failure, "timeout");
			throw failure;
		} catch (InterruptedException exception) {
			future.cancel(true);
			Thread.currentThread().interrupt();
			var failure = new AiServiceCallException(FallbackReason.AI_SERVICE_UNAVAILABLE, exception);
			recordFallback(timer, failure, "interrupted");
			throw failure;
		} catch (ExecutionException exception) {
			throw handleExecutionFailure(exception.getCause(), timer, traceId);
		}
	}

	private AnalysisResponse executeProtected(Ticket ticket, String traceId) {
		retryTraceId.set(traceId);
		try {
			Supplier<AnalysisResponse> call = () -> invoke(ticket, traceId);
			call = Retry.decorateSupplier(retry, call);
			call = CircuitBreaker.decorateSupplier(circuitBreaker, call);
			call = Bulkhead.decorateSupplier(bulkhead, call);
			return call.get();
		} finally {
			retryTraceId.remove();
		}
	}

	private RuntimeException handleExecutionFailure(
		Throwable cause,
		Timer.Sample timer,
		String traceId
	) {
		if (cause instanceof CallNotPermittedException exception) {
			meterRegistry.counter(METRIC_PREFIX + "circuit.rejected", "state", "open").increment();
			log.atWarn().addKeyValue("trace_id", traceId).log("ai.boundary.circuit_open");
			var failure = new AiServiceCallException(FallbackReason.AI_SERVICE_UNAVAILABLE, exception);
			recordFallback(timer, failure, "circuit_open");
			return failure;
		}
		if (cause instanceof BulkheadFullException exception) {
			meterRegistry.counter(METRIC_PREFIX + "bulkhead.rejected", "bulkhead", "ai").increment();
			log.atWarn().addKeyValue("trace_id", traceId).log("ai.boundary.bulkhead_rejected");
			var failure = new AiServiceCallException(FallbackReason.AI_SERVICE_UNAVAILABLE, exception);
			recordFallback(timer, failure, "bulkhead_rejected");
			return failure;
		}
		if (cause instanceof AiServiceCallException exception) {
			recordFallback(timer, exception, "transient_failure");
			return exception;
		}
		if (cause instanceof AiServiceAuthenticationException exception) {
			recordOutcome(timer, "rejected", "none");
			return exception;
		}
		if (cause instanceof AiServiceRequestException exception) {
			recordOutcome(timer, "rejected", "none");
			return exception;
		}
		if (cause instanceof AiServiceContractException exception) {
			recordOutcome(timer, "contract_error", "none");
			return exception;
		}
		recordOutcome(timer, "programming_error", "none");
		return new AiServiceContractException("Unexpected AI boundary failure.", cause);
	}

	private AnalysisResponse invoke(Ticket ticket, String traceId) {
		try {
			var response = restClient.post()
				.uri("/analyze")
				.header("X-Internal-Service-Token", internalServiceToken)
				.header(TraceId.HEADER_NAME, traceId)
				.body(new AnalyzeRequest(
					traceId,
					new TicketInput(
						ticket.getId(),
						ticket.getSubject(),
						ticket.getDescription(),
						ticket.getLanguage(),
						ticket.getCustomerTier(),
						ticket.getCategory(),
						ticket.getPriority()
					),
					new AnalyzeOptions(10, 3, AnalysisPolicy.VERSION)
				))
				.retrieve()
				.body(AnalysisResponse.class);
			validateResponse(response, traceId);
			recordAttempt("success");
			return response;
		} catch (HttpServerErrorException.GatewayTimeout exception) {
			recordAttempt("processing_timeout");
			meterRegistry.counter(METRIC_PREFIX + "timeouts", "stage", "python_deadline").increment();
			throw new AiServiceCallException(
				FallbackReason.PROCESSING_TIMEOUT,
				exception
			);
		} catch (HttpServerErrorException exception) {
			recordAttempt("transient_5xx");
			throw new AiTransientFailureException(
				FallbackReason.AI_SERVICE_ERROR,
				"transient_5xx",
				exception
			);
		} catch (HttpClientErrorException.TooManyRequests exception) {
			recordAttempt("transient_429");
			throw new AiTransientFailureException(
				FallbackReason.AI_SERVICE_ERROR,
				"transient_429",
				exception
			);
		} catch (HttpClientErrorException.Unauthorized | HttpClientErrorException.Forbidden exception) {
			recordAttempt("authentication_error");
			throw new AiServiceAuthenticationException(exception);
		} catch (HttpClientErrorException exception) {
			recordAttempt("request_error");
			throw new AiServiceRequestException(exception.getStatusCode().value(), exception);
		} catch (ResourceAccessException exception) {
			var timeout = hasTimeoutCause(exception);
			recordAttempt(timeout ? "timeout" : "unavailable");
			if (timeout) {
				meterRegistry.counter(METRIC_PREFIX + "timeouts", "stage", "java_deadline").increment();
			}
			throw new AiTransientFailureException(
				timeout ? FallbackReason.AI_SERVICE_TIMEOUT : FallbackReason.AI_SERVICE_UNAVAILABLE,
				timeout ? "timeout" : "unavailable",
				exception
			);
		} catch (RestClientResponseException exception) {
			recordAttempt("contract_error");
			throw new AiServiceContractException("AI service returned an unexpected HTTP response.", exception);
		} catch (RestClientException exception) {
			recordAttempt("contract_error");
			throw new AiServiceContractException("AI service returned a malformed success payload.", exception);
		}
	}

	private void validateResponse(AnalysisResponse response, String traceId) {
		if (response == null
			|| !AnalysisPolicy.VERSION.equals(response.promptVersion())
			|| !traceId.equals(response.traceId())
			|| !("live".equals(response.mode()) || "mock".equals(response.mode()) || "fallback".equals(response.mode()))) {
			throw new AiServiceContractException("AI service success payload violated the response contract.");
		}
	}

	private void recordAttempt(String outcome) {
		meterRegistry.counter(METRIC_PREFIX + "attempts", "outcome", outcome).increment();
	}

	private void recordFallback(Timer.Sample timer, AiServiceCallException exception, String outcome) {
		meterRegistry.counter(
			METRIC_PREFIX + "fallbacks",
			"reason",
			exception.getFallbackReason().value()
		).increment();
		recordOutcome(timer, outcome, "fallback");
	}

	private void recordOutcome(Timer.Sample timer, String outcome, String providerMode) {
		meterRegistry.counter(
			METRIC_PREFIX + "outcomes",
			"outcome",
			outcome,
			"provider_mode",
			providerMode
		).increment();
		timer.stop(Timer.builder(METRIC_PREFIX + "latency")
			.tag("outcome", outcome)
			.register(meterRegistry));
	}

	private String providerMode(AnalysisResponse response) {
		return switch (response.mode()) {
			case "live" -> "live";
			case "mock" -> "mock";
			case "fallback" -> "fallback";
			default -> "unknown";
		};
	}

	private String transientOutcome(Throwable throwable) {
		return throwable instanceof AiTransientFailureException failure
			? failure.outcome()
			: "unknown";
	}

	private boolean hasTimeoutCause(Throwable exception) {
		var current = exception;
		while (current != null) {
			if (current instanceof HttpTimeoutException) {
				return true;
			}
			current = current.getCause();
		}
		return false;
	}

	@PreDestroy
	void close() {
		deadlineExecutor.shutdownNow();
	}

	private record AnalyzeRequest(String traceId, TicketInput ticket, AnalyzeOptions options) {
	}

	private record TicketInput(
		String id,
		String subject,
		String description,
		String language,
		String customerTier,
		String currentCategory,
		String currentPriority
	) {
	}

	private record AnalyzeOptions(int topN, int topK, String promptVersion) {
	}
}
