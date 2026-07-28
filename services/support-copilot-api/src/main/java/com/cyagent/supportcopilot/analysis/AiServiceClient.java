package com.cyagent.supportcopilot.analysis;

import java.net.http.HttpClient;
import java.time.Duration;
import java.util.UUID;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import com.cyagent.supportcopilot.ticket.Ticket;

@Component
public class AiServiceClient {

	private final RestClient restClient;

	public AiServiceClient(
		@Value("${ai.service.base-url}") String baseUrl,
		@Value("${ai.service.timeout-ms}") long timeoutMs
	) {
		var timeout = Duration.ofMillis(timeoutMs);
		var httpClient = HttpClient.newBuilder()
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

	public AnalysisResponse analyze(Ticket ticket) {
		var request = new AnalyzeRequest(
			"trace_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12),
			new TicketInput(
				ticket.getId(),
				ticket.getSubject(),
				ticket.getDescription(),
				ticket.getLanguage(),
				ticket.getCustomerTier(),
				ticket.getCategory(),
				ticket.getPriority()
			),
			new AnalyzeOptions(10, 3, false, "ticket-analysis-v1")
		);

		return restClient.post()
			.uri("/analyze")
			.body(request)
			.retrieve()
			.body(AnalysisResponse.class);
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

	private record AnalyzeOptions(int topN, int topK, boolean enableRerank, String promptVersion) {
	}
}
