package com.cyagent.supportcopilot.common;

import java.util.ArrayList;
import java.util.Arrays;

import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.testcontainers.mysql.MySQLContainer;
import org.testcontainers.utility.DockerImageName;

import com.cyagent.supportcopilot.SupportCopilotApiApplication;

public final class MySqlTestSupport {

	public static final String IMAGE = "mysql:8.4.11-oraclelinux9@sha256:"
		+ "b3b90af2a6552ae30c266fdb7d5dd55f3afb72404bb78d37fe8a23eb857fd3fb";

	private MySqlTestSupport() {
	}

	public static MySQLContainer container(String databaseName) {
		var image = DockerImageName.parse(IMAGE).asCompatibleSubstituteFor("mysql");
		return new MySQLContainer(image)
			.withDatabaseName(databaseName)
			.withUsername("support_copilot")
			.withPassword("integration-only");
	}

	public static ConfigurableApplicationContext startContext(MySQLContainer mysql, String... properties) {
		return startContext(database(mysql), properties);
	}

	public static Database database(MySQLContainer mysql) {
		return new Database(mysql.getJdbcUrl(), mysql.getUsername(), mysql.getPassword());
	}

	public static Database database(MySQLContainer mysql, String databaseName) {
		var jdbcUrl = mysql.getJdbcUrl().replace(
			"/" + mysql.getDatabaseName(),
			"/" + databaseName
		);
		return new Database(jdbcUrl, mysql.getUsername(), mysql.getPassword());
	}

	public static Database createDatabase(MySQLContainer mysql, String databaseName) {
		if (!databaseName.matches("[a-z0-9_]+")) {
			throw new IllegalArgumentException("Unsafe MySQL test database name");
		}
		var rootDataSource = new DriverManagerDataSource(
			mysql.getJdbcUrl(),
			"root",
			mysql.getPassword()
		);
		var jdbc = new JdbcTemplate(rootDataSource);
		jdbc.execute("create database `" + databaseName + "`");
		jdbc.execute("grant all privileges on `" + databaseName + "`.* to 'support_copilot'@'%'");
		return database(mysql, databaseName);
	}

	public static ConfigurableApplicationContext startContext(Database database, String... properties) {
		var arguments = new ArrayList<>(Arrays.asList(
			"--spring.profiles.active=pilot",
			"--spring.datasource.url=" + database.jdbcUrl(),
			"--spring.datasource.username=" + database.username(),
			"--spring.datasource.password=" + database.password(),
			"--server.port=0",
			"--SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN=synthetic-mysql-integration-token",
			"--SUPPORT_COPILOT_JWT_ISSUER_URI=https://issuer.test/support-copilot",
			"--SUPPORT_COPILOT_JWT_JWK_SET_URI=https://issuer.test/support-copilot/jwks",
			"--SUPPORT_COPILOT_JWT_AUDIENCE=support-copilot-api"
		));
		arguments.addAll(Arrays.asList(properties));
		return new SpringApplicationBuilder(SupportCopilotApiApplication.class)
			.web(WebApplicationType.SERVLET)
			.run(arguments.toArray(String[]::new));
	}

	public record Database(String jdbcUrl, String username, String password) {
	}
}
