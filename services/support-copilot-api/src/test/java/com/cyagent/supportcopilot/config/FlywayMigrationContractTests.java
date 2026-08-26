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

	@Test
	void auditMigrationCreatesAppendOnlyQueryIndexesWithoutDestructiveStatements() throws IOException {
		var migration = new ClassPathResource("db/migration/V2__trusted_audit_events.sql")
			.getContentAsString(StandardCharsets.UTF_8)
			.toLowerCase();

		assertThat(migration)
			.contains("create table audit_events")
			.contains("actor_subject", "actor_type", "actor_roles_json")
			.contains("action", "target_type", "target_id", "target_version")
			.contains("trace_id", "metadata_json", "created_at")
			.contains("idx_audit_events_created", "idx_audit_events_target_created")
			.doesNotContain(
				"drop table",
				"truncate table",
				"delete from",
				"update audit_events",
				"flyway clean"
			);
	}

	@Test
	void idempotencyMigrationCreatesUniqueLeaseIndexedRecordsWithoutDestructiveStatements() throws IOException {
		var migration = new ClassPathResource("db/migration/V3__durable_command_idempotency.sql")
			.getContentAsString(StandardCharsets.UTF_8)
			.toLowerCase();

		assertThat(migration)
			.contains("create table command_idempotency")
			.contains("constraint uk_command_idempotency_key unique")
			.contains("idx_command_idempotency_pending_lease", "idx_command_idempotency_updated")
			.doesNotContain(
				"drop table", "truncate table", "delete from", "update command_idempotency", "flyway clean"
			);
	}
}
