package com.cyagent.supportcopilot.config;

import static com.cyagent.supportcopilot.common.MySqlTestSupport.container;
import static com.cyagent.supportcopilot.common.MySqlTestSupport.createDatabase;
import static com.cyagent.supportcopilot.common.MySqlTestSupport.startContext;
import static java.nio.charset.StandardCharsets.UTF_8;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.springframework.http.MediaType.APPLICATION_JSON;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.security.test.web.servlet.setup.SecurityMockMvcConfigurers.springSecurity;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Instant;

import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.exception.FlywayValidateException;
import org.hibernate.tool.schema.spi.SchemaManagementException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestReporter;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.mysql.MySQLContainer;

import tools.jackson.databind.ObjectMapper;

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
@Testcontainers
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

			assertThat(flyway.info().current().getVersion().getVersion()).isEqualTo("7");
			assertThat(flyway.info().applied())
				.hasSize(7)
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
	void migrationChecksumIsStableAndSecondMigrateIsANoOp() {
		var connection = createDatabase(MYSQL, "support_copilot_migration_repeat");
		var first = migrate(connection);
		var jdbc = jdbc(connection);
		var historyBefore = jdbc.queryForList("""
			select version, checksum, success
			from flyway_schema_history
			order by installed_rank
			""");

		var second = migrate(connection);

		assertThat(first.info().current().getVersion().getVersion()).isEqualTo("7");
		assertThat(second.info().current().getVersion().getVersion()).isEqualTo("7");
		assertThat(jdbc.queryForList("""
			select version, checksum, success
			from flyway_schema_history
			order by installed_rank
			"""))
			.isEqualTo(historyBefore);
	}

	@Test
	void httpTicketCreateAndReadUseMySqlAfterApplicationRestart() throws Exception {
		var connection = createDatabase(MYSQL, "support_copilot_http");
		var createRequest = """
			{"channel":"EMAIL","customerName":"MySQL HTTP Customer","customerCompany":"MySQL HTTP Company",
			"customerTier":"STANDARD","subject":"HTTP persistence","description":"Synthetic HTTP MySQL integration test.",
			"language":"en-US"}
			""";
		String ticketId;

		try (var context = startContext(connection)) {
			var mockMvc = mockMvc(context);
			var response = mockMvc.perform(post("/api/tickets")
					.with(jwt().jwt(jwt -> jwt.subject("mysql-http-agent"))
						.authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT")))
					.header("X-Trace-Id", "trace-mysql-http-create")
					.contentType(APPLICATION_JSON)
					.content(createRequest))
				.andExpect(status().isCreated())
				.andExpect(jsonPath("$.customerName").value("MySQL HTTP Customer"))
				.andExpect(jsonPath("$.customerCompany").value("MySQL HTTP Company"))
				.andExpect(jsonPath("$.category").value("UNCLASSIFIED"))
				.andExpect(jsonPath("$.status").value("NEW"))
				.andReturn();
			ticketId = context.getBean(ObjectMapper.class)
				.readTree(response.getResponse().getContentAsString())
				.get("id")
				.asString();
		}

		try (var restarted = startContext(connection)) {
			mockMvc(restarted).perform(get("/api/tickets/{id}", ticketId)
					.with(jwt().jwt(jwt -> jwt.subject("mysql-http-agent"))
						.authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT"))))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.id").value(ticketId))
				.andExpect(jsonPath("$.subject").value("HTTP persistence"))
				.andExpect(jsonPath("$.description").value("Synthetic HTTP MySQL integration test."))
				.andExpect(jsonPath("$.language").value("en-US"));
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

	private MockMvc mockMvc(ConfigurableApplicationContext context) {
		return MockMvcBuilders.webAppContextSetup((WebApplicationContext) context)
			.apply(springSecurity())
			.build();
	}
}
