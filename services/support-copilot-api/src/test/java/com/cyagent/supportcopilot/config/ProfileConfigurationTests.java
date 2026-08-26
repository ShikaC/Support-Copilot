package com.cyagent.supportcopilot.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.util.Properties;

import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

class ProfileConfigurationTests {

	@Test
	void isolatesDatabaseBehaviorAcrossNamedProfiles() throws IOException {
		var common = properties("application.properties");
		var demo = properties("application-demo.properties");
		var test = properties("application-test.properties");
		var local = properties("application-local.properties");
		var pilot = properties("application-pilot.properties");

		assertThat(common)
			.containsKeys("ai.service.base-url", "ai.service.timeout-ms", "evaluation.report-path")
			.doesNotContainKeys("spring.datasource.url", "spring.jpa.hibernate.ddl-auto");

		assertThat(demo)
			.containsEntry("spring.jpa.hibernate.ddl-auto", "create-drop")
			.containsEntry("spring.h2.console.enabled", "true")
			.containsEntry("support-copilot.demo-fixtures.enabled", "true");
		assertThat(test)
			.containsEntry("spring.jpa.hibernate.ddl-auto", "create-drop")
			.containsEntry("spring.h2.console.enabled", "false")
			.containsEntry("support-copilot.demo-fixtures.enabled", "false");

		assertMySqlProfile(local);
		assertMySqlProfile(pilot);
		assertRequiredDatabaseEnvironment(local);
		assertRequiredDatabaseEnvironment(pilot);
	}

	@Test
	void rejectsBlankRequiredDatabaseSettings() {
		assertThatThrownBy(() ->
			MySqlDataSourceConfiguration.requireNonBlankDatabaseSettings(" ", "user", "password"))
			.isInstanceOf(IllegalStateException.class)
			.hasMessageContaining("SUPPORT_COPILOT_DB_URL");
		assertThatThrownBy(() ->
			MySqlDataSourceConfiguration.requireNonBlankDatabaseSettings("jdbc:mysql://db", " ", "password"))
			.isInstanceOf(IllegalStateException.class)
			.hasMessageContaining("SUPPORT_COPILOT_DB_USERNAME");
		assertThatThrownBy(() ->
			MySqlDataSourceConfiguration.requireNonBlankDatabaseSettings("jdbc:mysql://db", "user", " "))
			.isInstanceOf(IllegalStateException.class)
			.hasMessageContaining("SUPPORT_COPILOT_DB_PASSWORD");
	}

	private static void assertRequiredDatabaseEnvironment(Properties properties) {
		assertThat(properties)
			.containsEntry("spring.datasource.url", "${SUPPORT_COPILOT_DB_URL}")
			.containsEntry("spring.datasource.username", "${SUPPORT_COPILOT_DB_USERNAME}")
			.containsEntry("spring.datasource.password", "${SUPPORT_COPILOT_DB_PASSWORD}");
	}

	private static void assertMySqlProfile(Properties properties) {
		assertThat(properties)
			.containsEntry("spring.jpa.hibernate.ddl-auto", "validate")
			.containsEntry("spring.flyway.enabled", "true")
			.containsEntry("spring.flyway.clean-disabled", "true")
			.containsEntry("spring.h2.console.enabled", "false")
			.containsEntry("support-copilot.demo-fixtures.enabled", "false");
		assertThat(properties.getProperty("spring.datasource.url")).doesNotContain("jdbc:h2:");
	}

	private static Properties properties(String path) throws IOException {
		var properties = new Properties();
		try (var input = new ClassPathResource(path).getInputStream()) {
			properties.load(input);
		}
		return properties;
	}
}
