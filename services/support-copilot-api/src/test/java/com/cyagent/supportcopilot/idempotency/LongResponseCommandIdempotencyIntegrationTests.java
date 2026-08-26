package com.cyagent.supportcopilot.idempotency;

import static com.cyagent.supportcopilot.idempotency.CommandIdempotencyAssertions.assertCounts;
import static java.nio.charset.StandardCharsets.UTF_8;
import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import tools.jackson.databind.ObjectMapper;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestReporter;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.jdbc.core.JdbcTemplate;

import com.cyagent.supportcopilot.analysis.AnalysisCommandService;
import com.cyagent.supportcopilot.analysis.AnalysisResponse;
import com.cyagent.supportcopilot.analysis.MockAnalysisFactory;
import com.cyagent.supportcopilot.common.TestTrustedActors;
import com.cyagent.supportcopilot.ticket.TicketRepository;

class LongResponseCommandIdempotencyIntegrationTests {

	private static final int ORDINARY_VARCHAR_LIMIT = 65_535;
	private static final int LARGE_REPLY_BYTES = 70 * 1_024;

	@Test
	void responseLargerThanOrdinaryVarcharSurvivesCompletionAndRestartReplayExactly(TestReporter testReporter)
		throws Exception {
		try (var rig = new CommandIdempotencyTestRig()) {
			var ticket = rig.ticket("ticket-long-response");
			var idempotencyKey = "analysis-long-response-key-0001";
			var longReply = "L".repeat(LARGE_REPLY_BYTES);
			AnalysisResponse original;
			String originalResponseJson;
			long originalResponseBytes;

			try (var first = rig.startContext()) {
				first.getBean(TicketRepository.class).saveAndFlush(ticket);
				var response = withReplyContent(
					first.getBean(MockAnalysisFactory.class).createMock(ticket),
					longReply
				);
				var objectMapper = first.getBean(ObjectMapper.class);
				var serializedResponse = objectMapper.writeValueAsString(response);
				assertThat(serializedResponse.getBytes(UTF_8).length)
					.as("controlled response JSON UTF-8 byte length")
					.isGreaterThan(ORDINARY_VARCHAR_LIMIT);
				rig.aiServer().respondWith(serializedResponse);

				original = analyze(first, ticket.getId(), idempotencyKey);
				assertThat(original)
					.usingRecursiveComparison()
					.ignoringFields("traceId")
					.isEqualTo(response);
				assertThat(rig.aiServer().invocations()).isEqualTo(1);
				assertCounts(first, 1, 0, 1, 1);

				var jdbc = first.getBean(JdbcTemplate.class);
				var correlatedResponseJson = objectMapper.writeValueAsString(original);
				originalResponseJson = commandResponseJson(jdbc, idempotencyKey);
				originalResponseBytes = commandResponseBytes(jdbc, idempotencyKey);
				testReporter.publishEntry(
					"persistedCommandResponseUtf8Bytes",
					Long.toString(originalResponseBytes)
				);
				assertThat(originalResponseJson.getBytes(UTF_8))
					.containsExactly(correlatedResponseJson.getBytes(UTF_8));
				assertThat(originalResponseBytes).isGreaterThan(ORDINARY_VARCHAR_LIMIT);
				assertThat(analysisResponseBytes(jdbc, original.id())).isGreaterThan(ORDINARY_VARCHAR_LIMIT);
				assertThat(commandState(jdbc, idempotencyKey)).isEqualTo("COMPLETED");
				assertThat(commandResponseStatus(jdbc, idempotencyKey)).isEqualTo(200);
			}

			try (var restarted = rig.startContext()) {
				var replay = analyze(restarted, ticket.getId(), idempotencyKey);
				assertThat(replay).isEqualTo(original);
				assertThat(replay.suggestedReply().content().getBytes(UTF_8))
					.containsExactly(longReply.getBytes(UTF_8));
				assertThat(rig.aiServer().invocations()).isEqualTo(1);
				assertCounts(restarted, 1, 0, 1, 1);

				var jdbc = restarted.getBean(JdbcTemplate.class);
				assertThat(commandResponseJson(jdbc, idempotencyKey)).isEqualTo(originalResponseJson);
				assertThat(commandResponseBytes(jdbc, idempotencyKey)).isEqualTo(originalResponseBytes);
				assertThat(commandState(jdbc, idempotencyKey)).isEqualTo("COMPLETED");
				assertThat(commandResponseStatus(jdbc, idempotencyKey)).isEqualTo(200);
			}
		}
	}

	private AnalysisResponse withReplyContent(AnalysisResponse response, String content) {
		return new AnalysisResponse(
			response.id(), response.traceId(), response.status(), response.mode(), response.fallbackReason(),
			response.modelName(), response.promptVersion(), response.classification(), response.workflowSteps(),
			response.retrieval(), new AnalysisResponse.SuggestedReply(content, List.of(), List.of()),
			response.decision(), response.usage(), response.createdAt()
		);
	}

	private AnalysisResponse analyze(ConfigurableApplicationContext context, String ticketId, String key) {
		TestTrustedActors.authenticate("task-6-long-response-agent", "SUPPORT_AGENT");
		try {
			return context.getBean(AnalysisCommandService.class).analyze(ticketId, IdempotencyKey.parse(key));
		} finally {
			TestTrustedActors.clear();
		}
	}

	private String commandResponseJson(JdbcTemplate jdbc, String key) {
		return jdbc.queryForObject(
			"select response_json from command_idempotency where idempotency_key = ?", String.class, key
		);
	}

	private long commandResponseBytes(JdbcTemplate jdbc, String key) {
		return jdbc.queryForObject(
			"select octet_length(response_json) from command_idempotency where idempotency_key = ?", Long.class, key
		);
	}

	private long analysisResponseBytes(JdbcTemplate jdbc, String analysisId) {
		return jdbc.queryForObject(
			"select octet_length(response_json) from analysis_runs where id = ?", Long.class, analysisId
		);
	}

	private int commandResponseStatus(JdbcTemplate jdbc, String key) {
		return jdbc.queryForObject(
			"select response_http_status from command_idempotency where idempotency_key = ?", Integer.class, key
		);
	}

	private String commandState(JdbcTemplate jdbc, String key) {
		return jdbc.queryForObject(
			"select status from command_idempotency where idempotency_key = ?", String.class, key
		);
	}
}
