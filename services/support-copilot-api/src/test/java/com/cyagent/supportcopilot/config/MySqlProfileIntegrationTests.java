package com.cyagent.supportcopilot.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.http.MediaType.APPLICATION_JSON;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Instant;

import jakarta.persistence.EntityManager;

import org.hibernate.tool.schema.spi.SchemaManagementException;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.context.WebApplicationContext;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.mysql.MySQLContainer;
import org.testcontainers.utility.DockerImageName;

import com.cyagent.supportcopilot.analysis.AnalysisRun;
import com.cyagent.supportcopilot.analysis.AnalysisRunRepository;
import com.cyagent.supportcopilot.analysis.review.AnalysisReview;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewAction;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewRepository;
import com.cyagent.supportcopilot.SupportCopilotApiApplication;
import com.cyagent.supportcopilot.ticket.TicketRepository;

@SpringBootTest
@ActiveProfiles("pilot")
@EnabledIfEnvironmentVariable(named = "SUPPORT_COPILOT_RUN_MYSQL_TESTS", matches = "true")
@Testcontainers(disabledWithoutDocker = true)
class MySqlProfileIntegrationTests {

	@Container
	static final MySQLContainer MYSQL = new MySQLContainer(DockerImageName.parse("mysql:8.0.36"))
		.withDatabaseName("support_copilot")
		.withUsername("support_copilot")
		.withPassword("integration-only");

	@Container
	static final MySQLContainer STALE_MYSQL = new MySQLContainer(DockerImageName.parse("mysql:8.0.36"))
		.withDatabaseName("unmigrated_support_copilot")
		.withUsername("support_copilot")
		.withPassword("integration-only");

	@DynamicPropertySource
	static void mysqlProperties(DynamicPropertyRegistry registry) {
		registry.add("spring.datasource.url", MYSQL::getJdbcUrl);
		registry.add("spring.datasource.username", MYSQL::getUsername);
		registry.add("spring.datasource.password", MYSQL::getPassword);
	}

	@Autowired
	private TicketRepository ticketRepository;

	@Autowired
	private AnalysisRunRepository analysisRunRepository;

	@Autowired
	private AnalysisReviewRepository analysisReviewRepository;

	@Autowired
	private JdbcTemplate jdbcTemplate;

	@Autowired
	private Flyway flyway;

	@Autowired
	private EntityManager entityManager;

	@Autowired
	private WebApplicationContext applicationContext;

	private MockMvc mockMvc;

	@BeforeEach
	void setUpMockMvc() {
		mockMvc = MockMvcBuilders.webAppContextSetup(applicationContext).build();
	}

	@Test
	@Transactional
	void appliesSchemaAndPreservesCurrentRepositoryAndApiMappings() throws Exception {
		assertThat(ticketRepository.count()).isZero();
		assertThat(analysisRunRepository.count()).isZero();

		var createResult = mockMvc.perform(post("/api/tickets")
			.contentType(APPLICATION_JSON)
			.content("""
				{
				  "channel": "EMAIL",
				  "customerName": "Persistence Sentinel",
				  "customerCompany": "Task 3 Verification",
				  "customerTier": "STANDARD",
				  "subject": "Verify MySQL persistence",
				  "description": "Synthetic integration-test ticket.",
				  "language": "en-US"
				}
				"""))
			.andExpect(status().isCreated())
			.andExpect(jsonPath("$.version").value(0))
			.andReturn();
		var ticketId = com.jayway.jsonpath.JsonPath.<String>read(
			createResult.getResponse().getContentAsString(), "$.id");

		mockMvc.perform(patch("/api/tickets/{id}", ticketId)
			.contentType(APPLICATION_JSON)
			.content("""
				{"status":"IN_PROGRESS","priority":"HIGH","expectedVersion":0}
				"""))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.id").value(ticketId))
			.andExpect(jsonPath("$.version").value(1));

		var observedAt = Instant.parse("2026-08-26T12:34:56.123456Z");
		var longContent = "x".repeat(70_000);
		var run = new AnalysisRun();
		run.setId("analysis-mysql-mapping");
		run.setTicketId(ticketId);
		run.setSourceTicketVersion(1);
		run.setTraceId("task-3-mysql-mapping");
		run.setStatus("SUCCEEDED");
		run.setMode("mock");
		run.setResponseJson(longContent);
		run.setCreatedAt(observedAt);
		analysisRunRepository.saveAndFlush(run);

		var review = new AnalysisReview();
		review.setId("review-mysql-mapping");
		review.setTicketId(ticketId);
		review.setAnalysisId(run.getId());
		review.setAction(AnalysisReviewAction.EDITED);
		review.setReviewerType("DEMO_USER");
		review.setReviewerLabel("Persistence Test");
		review.setOriginalReplyContent(longContent);
		review.setReviewedReplyContent(longContent + "-reviewed");
		review.setTicketVersion(1);
		review.setTraceId(run.getTraceId());
		review.setCreatedAt(observedAt);
		analysisReviewRepository.saveAndFlush(review);
		entityManager.clear();

		assertThat(analysisRunRepository.findById(run.getId()).orElseThrow().getResponseJson())
			.hasSize(70_000);
		assertThat(analysisRunRepository.findById(run.getId()).orElseThrow().getCreatedAt())
			.isEqualTo(observedAt);
		assertThat(analysisReviewRepository.findById(review.getId()).orElseThrow().getReviewedReplyContent())
			.endsWith("-reviewed");
		assertThat(ticketRepository.findById(ticketId).orElseThrow().getVersion()).isEqualTo(1);

		assertThat(columnType("analysis_runs", "response_json")).isEqualTo("longtext");
		assertThat(columnType("analysis_runs", "created_at")).isEqualTo("datetime");
		assertThat(columnType("tickets", "version")).isEqualTo("bigint");
	}

	@Test
	void migrationChecksumIsStableAndSecondMigrateIsANoOp() {
		var migration = flyway.info().current();

		assertThat(migration).isNotNull();
		assertThat(migration.getVersion().getVersion()).isEqualTo("3");
		assertThat(migration.getChecksum()).isNotNull();
		assertThat(flyway.migrate().migrationsExecuted).isZero();
		assertThat(flyway.info().current().getChecksum()).isEqualTo(migration.getChecksum());
	}

	@Test
	void hibernateValidationRejectsAnUnmigratedSchema() {
		assertThat(org.assertj.core.api.Assertions.catchThrowable(() ->
			new SpringApplicationBuilder(SupportCopilotApiApplication.class)
				.web(WebApplicationType.NONE)
				.run(
					"--spring.profiles.active=pilot",
					"--spring.datasource.url=" + STALE_MYSQL.getJdbcUrl(),
					"--spring.datasource.username=" + STALE_MYSQL.getUsername(),
					"--spring.datasource.password=" + STALE_MYSQL.getPassword(),
					"--spring.flyway.enabled=false"
				)
		))
			.hasRootCauseInstanceOf(SchemaManagementException.class)
			.hasStackTraceContaining("Schema-validation: missing table");
	}

	private String columnType(String table, String column) {
		return jdbcTemplate.queryForObject("""
			SELECT DATA_TYPE
			FROM information_schema.columns
			WHERE table_schema = DATABASE() AND table_name = ? AND column_name = ?
			""", String.class, table, column);
	}
}
