package com.cyagent.supportcopilot.knowledge;

import static com.cyagent.supportcopilot.common.MySqlTestSupport.container;
import static com.cyagent.supportcopilot.common.MySqlTestSupport.startContext;
import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.mysql.MySQLContainer;

import com.cyagent.supportcopilot.common.TestTrustedActors;
import com.cyagent.supportcopilot.knowledge.KnowledgeReleaseDtos.CreateReleaseRequest;

@EnabledIfEnvironmentVariable(named = "SUPPORT_COPILOT_RUN_MYSQL_TESTS", matches = "true")
@Testcontainers
class KnowledgeReleaseMySqlIntegrationTests {
	private static final String CANDIDATE_RELEASE_ID = "mysql-release-candidate";

	@Container
	static final MySQLContainer MYSQL = container("support_copilot_knowledge");

	@Test
	void publishAndRollbackActivePointerSurvivesApplicationRestart() {
		String baselineReleaseId;
		int baselineReleaseVersion;
		String baselineChecksum;
		try (var context = startContext(MYSQL)) {
			var service = context.getBean(KnowledgeReleaseService.class);
			try {
				var baseline = service.active();
				baselineReleaseId = baseline.releaseId();
				baselineReleaseVersion = baseline.releaseVersion();
				baselineChecksum = baseline.corpusChecksum();
				assertThat(baseline.status()).isEqualTo(KnowledgeReleaseStatus.PUBLISHED);

				TestTrustedActors.authenticate("mysql-knowledge-reviewer", "SUPPORT_REVIEWER");
				service.create(release(
					CANDIDATE_RELEASE_ID,
					baselineReleaseVersion + 1,
					"c".repeat(64),
					"BILLING"
				));
				service.approve(CANDIDATE_RELEASE_ID, 0);
				TestTrustedActors.authenticate("mysql-knowledge-admin", "SUPPORT_ADMIN");
				service.publish(CANDIDATE_RELEASE_ID, 1);

				var archivedBaseline = context.getBean(KnowledgeReleaseRepository.class)
					.findById(baselineReleaseId).orElseThrow();
				assertThat(archivedBaseline.getStatus()).isEqualTo(KnowledgeReleaseStatus.ARCHIVED);
				service.rollback(baselineReleaseId, archivedBaseline.getVersion());
				assertThat(service.active().releaseId()).isEqualTo(baselineReleaseId);
			} finally {
				TestTrustedActors.clear();
			}
		}

		try (var restarted = startContext(MYSQL)) {
			var service = restarted.getBean(KnowledgeReleaseService.class);
			var active = service.active();
			assertThat(active.releaseId()).isEqualTo(baselineReleaseId);
			assertThat(active.releaseVersion()).isEqualTo(baselineReleaseVersion);
			assertThat(active.corpusChecksum()).isEqualTo(baselineChecksum);
			assertThat(active.status()).isEqualTo(KnowledgeReleaseStatus.PUBLISHED);
			assertThat(service.get(CANDIDATE_RELEASE_ID).status()).isEqualTo(KnowledgeReleaseStatus.ARCHIVED);
			assertThat(restarted.getBean(JdbcTemplate.class).queryForObject(
				"select count(*) from audit_events where action = 'KNOWLEDGE_RELEASE_ROLLED_BACK' "
					+ "and target_id = ?",
				Long.class,
				baselineReleaseId
			)).isEqualTo(1);
		}
	}

	private CreateReleaseRequest release(String id, int version, String checksum, String scope) {
		return new CreateReleaseRequest(id, version, checksum, List.of(scope));
	}
}
