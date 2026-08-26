package com.cyagent.supportcopilot.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

class FlywayMigrationContractTests {

	@Test
	void baselineCreatesCurrentJpaSchemaWithoutDestructiveStatements() throws IOException {
		var migration = new ClassPathResource("db/migration/V1__baseline.sql")
			.getContentAsString(StandardCharsets.UTF_8)
			.toLowerCase();

		assertThat(migration)
			.contains("create table tickets", "create table analysis_runs", "create table analysis_reviews")
			.contains("unique", "index")
			.doesNotContain("drop table", "truncate table", "delete from", "flyway clean");
	}
}
