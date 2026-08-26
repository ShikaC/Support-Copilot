package com.cyagent.supportcopilot.idempotency;

import static org.assertj.core.api.Assertions.assertThat;

import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.mysql.MySQLContainer;
import org.testcontainers.utility.DockerImageName;

@SpringBootTest
@ActiveProfiles("pilot")
@EnabledIfEnvironmentVariable(named = "SUPPORT_COPILOT_RUN_MYSQL_TESTS", matches = "true")
@Testcontainers(disabledWithoutDocker = true)
class CommandIdempotencyMySqlIntegrationTests {

	@Container
	static final MySQLContainer MYSQL = new MySQLContainer(DockerImageName.parse("mysql:8.0.36"))
		.withDatabaseName("support_copilot_idempotency")
		.withUsername("support_copilot")
		.withPassword("integration-only");

	@DynamicPropertySource
	static void mysqlProperties(DynamicPropertyRegistry registry) {
		registry.add("spring.datasource.url", MYSQL::getJdbcUrl);
		registry.add("spring.datasource.username", MYSQL::getUsername);
		registry.add("spring.datasource.password", MYSQL::getPassword);
	}

	@Autowired
	private Flyway flyway;

	@Autowired
	private JdbcTemplate jdbcTemplate;

	@Test
	void appliesV3WithLongTextResponseAndGlobalKeyUniqueness() {
		assertThat(flyway.info().current().getVersion().getVersion()).isEqualTo("3");
		assertThat(columnType("response_json")).isEqualTo("longtext");
		assertThat(columnType("request_fingerprint")).isEqualTo("char");
		assertThat(jdbcTemplate.queryForObject("""
			select count(*) from information_schema.table_constraints
			where table_schema = database()
			  and table_name = 'command_idempotency'
			  and constraint_name = 'uk_command_idempotency_key'
			  and constraint_type = 'UNIQUE'
			""", Long.class)).isEqualTo(1);
	}

	@Test
	void secondMigrateIsANoOpAtV3() {
		assertThat(flyway.migrate().migrationsExecuted).isZero();
		assertThat(flyway.info().current().getVersion().getVersion()).isEqualTo("3");
	}

	private String columnType(String column) {
		return jdbcTemplate.queryForObject("""
			select data_type from information_schema.columns
			where table_schema = database()
			  and table_name = 'command_idempotency'
			  and column_name = ?
			""", String.class, column);
	}
}
