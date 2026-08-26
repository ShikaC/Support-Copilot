package com.cyagent.supportcopilot.config;

import javax.sql.DataSource;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.jdbc.autoconfigure.DataSourceProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;

@Configuration(proxyBeanMethods = false)
@Profile({"local", "pilot"})
class MySqlDataSourceConfiguration {

	@Bean
	DataSource dataSource(
		DataSourceProperties properties,
		@Value("${spring.datasource.url}") String url,
		@Value("${spring.datasource.username}") String username,
		@Value("${spring.datasource.password}") String password
	) {
		requireNonBlankDatabaseSettings(url, username, password);
		return properties.initializeDataSourceBuilder().build();
	}

	static void requireNonBlankDatabaseSettings(String url, String username, String password) {
		requireNonBlank(url, "SUPPORT_COPILOT_DB_URL");
		requireNonBlank(username, "SUPPORT_COPILOT_DB_USERNAME");
		requireNonBlank(password, "SUPPORT_COPILOT_DB_PASSWORD");
	}

	private static void requireNonBlank(String value, String environmentVariable) {
		if (value == null || value.isBlank()) {
			throw new IllegalStateException(environmentVariable + " must be configured with a non-blank value");
		}
	}
}
