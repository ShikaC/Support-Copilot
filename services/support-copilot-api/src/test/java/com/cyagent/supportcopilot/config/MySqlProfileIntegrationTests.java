package com.cyagent.supportcopilot.config;

import static com.cyagent.supportcopilot.common.MySqlTestSupport.container;
import static com.cyagent.supportcopilot.common.MySqlTestSupport.createDatabase;
import static com.cyagent.supportcopilot.common.MySqlTestSupport.startContext;
import static java.nio.charset.StandardCharsets.UTF_8;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;

import java.time.Instant;

import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.exception.FlywayValidateException;
import org.hibernate.tool.schema.spi.SchemaManagementException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestReporter;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.mysql.MySQLContainer;

import com.cyagent.supportcopilot.analysis.AnalysisRun;
import com.cyagent.supportcopilot.analysis.AnalysisRunRepository;
import com.cyagent.supportcopilot.analysis.review.AnalysisReview;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewAction;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewRepository;
import com.cyagent.supportcopilot.common.MySqlTestSupport.Database;
import com.cyagent.supportcopilot.common.TestTrustedActors;
import com.cyagent.supportcopilot.ticket.TicketDtos.CreateTicketRequest;
import com.cyagent.supportcopilot.ticket.TicketDomain.Channel;
import com.cyagent.supportcopilot.ticket.TicketDomain.CustomerTier;
import com.cyagent.supportcopilot.ticket.TicketService;

@EnabledIfEnvironmentVariable(named = "SUPPORT_COPILOT_RUN_MYSQL_TESTS", matches = "true")
@Testcontainers(disabledWithoutDocker = true)
class MySqlProfileIntegrationTests {
	private static final int MYSQL_TEXT_MAX_BYTES = 65_535;
	private static final int LARGE_PAYLOAD_BYTES = 100_000;

	@Container
	static final MySQLContainer MYSQL = container("support_copilot_profile");

	@Test
	void migratedPilotSchemaStartsWithoutDemoTickets() {
		try (var context = startContext(MYSQL)) {
			var flyway = context.getBean(Flyway.class);
			var jdbc = context.getBean(JdbcTemplate.class);

			assertThat(flyway.info().current().getVersion().getVersion()).isEqualTo("5");
			assertThat(flyway.info().applied())
				.hasSize(5)
				.allSatisfy(migration -> assertThat(migration.getChecksum()).isNotNull());
			assertThat(jdbc.queryForObject("select count(*) from tickets", Long.class)).isZero();
		}
	}

	@Test
	void largeAnalysisAndReviewPayloadsRoundTripExactlyAfterRestart(TestReporter testReporter) {
		var connection = createDatabase(MYSQL, "support_copilot_large_payload");
		var analysisPayload = "A".repeat(LARGE_PAYLOAD_BYTES);
		var reviewedPayload = "R".repeat(LARGE_PAYLOAD_BYTES);

		try (var context = startContext(connection)) {
			TestTrustedActors.authenticate("mysql-large-payload-agent", "SUPPORT_AGENT");
			try {
				var ticket = context.getBean(TicketService.class).create(new CreateTicketRequest(
					Channel.EMAIL,
					"Synthetic MySQL Customer",
					"Task 15 Verification",
					CustomerTier.STANDARD,
					"Large payload round trip",
					"Synthetic persistence test data.",
					"en-US"
				));
				var observedAt = Instant.parse("2026-08-30T12:34:56.123456Z");
				var run = new AnalysisRun();
				run.setId("analysis-mysql-large-payload");
				run.setTicketId(ticket.id());
				run.setSourceTicketVersion(ticket.version());
				run.setTraceId("trace-mysql-large-payload");
				run.setStatus("SUCCEEDED");
				run.setMode("mock");
				run.setResponseJson(analysisPayload);
				run.setCreatedAt(observedAt);
				context.getBean(AnalysisRunRepository.class).saveAndFlush(run);

				var review = new AnalysisReview();
				review.setId("review-mysql-large-payload");
				review.setTicketId(ticket.id());
				review.setAnalysisId(run.getId());
				review.setAction(AnalysisReviewAction.EDITED);
				review.setReviewerType("SUPPORT_AGENT");
				review.setReviewerLabel("MySQL Persistence Test");
				review.setOriginalReplyContent(analysisPayload);
				review.setReviewedReplyContent(reviewedPayload);
				review.setTicketVersion(ticket.version());
				review.setTraceId(run.getTraceId());
				review.setCreatedAt(observedAt);
				context.getBean(AnalysisReviewRepository.class).saveAndFlush(review);
			} finally {
				TestTrustedActors.clear();
			}
		}

		try (var restarted = startContext(connection)) {
			var storedAnalysis = restarted.getBean(AnalysisRunRepository.class)
				.findById("analysis-mysql-large-payload").orElseThrow();
			var storedReview = restarted.getBean(AnalysisReviewRepository.class)
				.findById("review-mysql-large-payload").orElseThrow();
			assertThat(storedAnalysis.getResponseJson()).isEqualTo(analysisPayload);
			assertThat(storedReview.getOriginalReplyContent()).isEqualTo(analysisPayload);
			assertThat(storedReview.getReviewedReplyContent()).isEqualTo(reviewedPayload);
			assertThat(storedAnalysis.getResponseJson().getBytes(UTF_8).length)
				.isGreaterThan(MYSQL_TEXT_MAX_BYTES);
			testReporter.publishEntry("mysqlLargePayloadUtf8Bytes", Integer.toString(LARGE_PAYLOAD_BYTES));
		}
	}

	@Test
	void tamperedMigrationHistoryPreventsPilotStartup() {
		var connection = createDatabase(MYSQL, "support_copilot_checksum");
		migrate(connection);
		jdbc(connection).update(
			"update flyway_schema_history set checksum = checksum + 1 where version = '4'"
		);

		var failure = catchThrowable(() -> startContext(connection));

		assertThat(failure)
			.isNotNull()
			.hasRootCauseInstanceOf(FlywayValidateException.class);
	}

	@Test
	void missingKnowledgeActivePointerColumnPreventsPilotStartup() {
		var connection = createDatabase(MYSQL, "support_copilot_drift");
		migrate(connection);
		var jdbc = jdbc(connection);
		jdbc.execute("alter table knowledge_active_release drop foreign key fk_knowledge_active_release");
		jdbc.execute("alter table knowledge_active_release drop column release_id");

		var failure = catchThrowable(() -> startContext(
			connection,
			"--spring.flyway.enabled=false"
		));

		assertThat(failure)
			.isNotNull()
			.hasRootCauseInstanceOf(SchemaManagementException.class);
	}

	private Flyway migrate(Database database) {
		var flyway = Flyway.configure()
			.dataSource(database.jdbcUrl(), database.username(), database.password())
			.load();
		flyway.migrate();
		return flyway;
	}

	private JdbcTemplate jdbc(Database database) {
		return new JdbcTemplate(new DriverManagerDataSource(
			database.jdbcUrl(),
			database.username(),
			database.password()
		));
	}
}
