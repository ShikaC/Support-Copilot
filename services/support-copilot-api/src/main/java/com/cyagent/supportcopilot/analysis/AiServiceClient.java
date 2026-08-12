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

	public AnalysisResponse analyze(Ticket ticket) {
		// 这个 DTO 是 Java 业务 API 与 Python AI/RAG 服务之间的契约。
		// 修改这里时，必须同时确认 services/support-copilot-ai/app/models.py 仍然兼容。
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
			new AnalyzeOptions(10, 3, "ticket-analysis-v1")
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

	private record AnalyzeOptions(int topN, int topK, String promptVersion) {
	}
}
