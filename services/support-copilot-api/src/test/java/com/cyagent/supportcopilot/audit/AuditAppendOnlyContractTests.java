package com.cyagent.supportcopilot.audit;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import org.junit.jupiter.api.Test;

class AuditAppendOnlyContractTests {

	private static final Path AUDIT_SOURCE = Path.of(
		"src/main/java/com/cyagent/supportcopilot/audit"
	);

	@Test
	void applicationRepositoryExposesInsertAndQueryOnly() throws IOException {
		var source = Files.readString(AUDIT_SOURCE.resolve("AuditEventRepository.java"));

		assertThat(source)
			.contains("void insert(AuditEvent event)", "List<AuditEvent> query(AuditEventQuery query)")
			.doesNotContain("save(", "delete", "update", "JpaRepository", "CrudRepository");
	}

	@Test
	void auditEntityHasNoMutableFieldApiAndColumnsAreNotUpdatable() throws IOException {
		var source = Files.readString(AUDIT_SOURCE.resolve("AuditEvent.java"));

		assertThat(source)
			.contains("updatable = false")
			.doesNotContain("@Setter", " void set", "public void set");
	}

	@Test
	void auditControllerHasNoWriteUpdateOrDeleteEndpoint() throws IOException {
		var source = Files.readString(AUDIT_SOURCE.resolve("AuditEventController.java"));

		assertThat(source)
			.contains("@GetMapping")
			.doesNotContain("@PostMapping", "@PutMapping", "@PatchMapping", "@DeleteMapping");
	}
}
