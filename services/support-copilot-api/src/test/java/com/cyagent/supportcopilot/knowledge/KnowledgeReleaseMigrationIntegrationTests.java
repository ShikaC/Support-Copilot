package com.cyagent.supportcopilot.knowledge;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.UUID;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.AfterAll;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@SpringBootTest(properties = "spring.jpa.hibernate.ddl-auto=validate")
@ActiveProfiles("test")
@DirtiesContext
class KnowledgeReleaseMigrationIntegrationTests {

	private static final String DATABASE_URL = "jdbc:h2:mem:knowledge-release-migration-"
		+ UUID.randomUUID() + ";MODE=MySQL;DB_CLOSE_DELAY=-1;DB_CLOSE_ON_EXIT=FALSE";
	private static final Connection KEEP_ALIVE = openConnection();

	static {
		Flyway.configure().dataSource(DATABASE_URL, "sa", "").load().migrate();
	}

	@AfterAll
	static void closeDatabase() throws SQLException {
		KEEP_ALIVE.close();
	}

	@DynamicPropertySource
	static void databaseProperties(DynamicPropertyRegistry registry) {
		registry.add("spring.datasource.url", () -> DATABASE_URL);
		registry.add("spring.flyway.enabled", () -> false);
	}

	@Autowired
	private JdbcTemplate jdbcTemplate;

	@Test
	void flywayV4MigratesH2AndBaselineActivationPassesHibernateValidation() {
		assertThat(jdbcTemplate.queryForObject(
			"select \"version\" from \"flyway_schema_history\" where \"success\" = true "
				+ "order by \"installed_rank\" desc limit 1",
			String.class
		)).isEqualTo("4");
		assertThat(jdbcTemplate.queryForObject(
			"select release_id from knowledge_active_release where id = 'active'",
			String.class
		)).isEqualTo("bundled-v1");
		assertThat(jdbcTemplate.queryForObject(
			"select status from knowledge_releases where release_id = 'bundled-v1'",
			String.class
		)).isEqualTo("PUBLISHED");
	}

	private static Connection openConnection() {
		try {
			return DriverManager.getConnection(DATABASE_URL, "sa", "");
		} catch (SQLException exception) {
			throw new ExceptionInInitializerError(exception);
		}
	}
}
