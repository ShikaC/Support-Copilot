package com.cyagent.supportcopilot.analysis;

import java.net.http.HttpClient;
import java.net.http.HttpTimeoutException;
import java.time.Duration;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

import com.cyagent.supportcopilot.ticket.Ticket;
import com.cyagent.supportcopilot.common.TraceId;

@Component
public class AiServiceClient {

	private final RestClient restClient;
	private final String internalServiceToken;

	public AiServiceClient(
		@Value("${ai.service.base-url}") String baseUrl,
		@Value("${ai.service.timeout-ms}") long timeoutMs,
		@Value("${support-copilot.security.internal-service-token}") String internalServiceToken
	) {
		if (internalServiceToken.isBlank()) {
			throw new IllegalStateException(
				"SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN must be configured with a non-blank value."
			);
		}
		this.internalServiceToken = internalServiceToken;
		var timeout = Duration.ofMillis(timeoutMs);
		var httpClient = HttpClient.newBuilder()
			// 这里要强制使用普通 HTTP/1.1。
			// 否则 Java 可能尝试 h2c 协商，导致 Uvicorn 拒绝 AI 服务请求。
			.version(HttpClient.Version.HTTP_1_1)
			.connectTimeout(timeout)
			.build();
		var requestFactory = new JdkClientHttpRequestFactory(httpClient);
		requestFactory.setReadTimeout(timeout);
		this.restClient = RestClient.builder()
			.baseUrl(baseUrl)
			.requestFactory(requestFactory)
			.build();
	}

	public AnalysisResponse analyze(Ticket ticket, String traceId) {
		// 这个 DTO 是 Java 业务 API 与 Python AI/RAG 服务之间的契约。
		// 修改这里时，必须同时确认 services/support-copilot-ai/app/models.py 仍然兼容。
		var request = new AnalyzeRequest(
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
		);

		try {
			var response = restClient.post()
				.uri("/analyze")
				.header("X-Internal-Service-Token", internalServiceToken)
				.header(TraceId.HEADER_NAME, traceId)
				.body(request)
				.retrieve()
				.body(AnalysisResponse.class);
			if (response == null || !AnalysisPolicy.VERSION.equals(response.promptVersion())) {
				throw new AiServiceCallException(FallbackReason.INVALID_AI_RESPONSE);
			}
			return response;
		} catch (HttpServerErrorException.GatewayTimeout exception) {
			throw new AiServiceCallException(FallbackReason.PROCESSING_TIMEOUT, exception);
		} catch (HttpClientErrorException.Unauthorized | HttpClientErrorException.Forbidden exception) {
			throw new AiServiceAuthenticationException(exception);
		} catch (HttpClientErrorException exception) {
			throw new AiServiceRequestException(exception.getStatusCode().value(), exception);
		} catch (ResourceAccessException exception) {
			var reason = hasTimeoutCause(exception)
				? FallbackReason.AI_SERVICE_TIMEOUT
				: FallbackReason.AI_SERVICE_UNAVAILABLE;
			throw new AiServiceCallException(reason, exception);
		} catch (RestClientResponseException exception) {
			throw new AiServiceCallException(FallbackReason.AI_SERVICE_ERROR, exception);
		} catch (RestClientException exception) {
			throw new AiServiceCallException(FallbackReason.INVALID_AI_RESPONSE, exception);
		}
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
