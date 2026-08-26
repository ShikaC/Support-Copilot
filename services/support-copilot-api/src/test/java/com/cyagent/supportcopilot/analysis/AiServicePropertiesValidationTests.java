package com.cyagent.supportcopilot.analysis;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.util.Properties;

import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.context.properties.bind.validation.BindValidationException;
import org.springframework.boot.test.context.ConfigDataApplicationContextInitializer;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.ClassPathResource;

class AiServicePropertiesValidationTests {

	private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
		.withInitializer(new ConfigDataApplicationContextInitializer())
		.withUserConfiguration(PropertiesConfiguration.class);

	@Test
	void defaultTwoTotalAttemptsBindsSuccessfully() throws IOException {
		var applicationProperties = new Properties();
		try (var input = new ClassPathResource("application.properties").getInputStream()) {
			applicationProperties.load(input);
		}
		assertThat(applicationProperties)
			.containsEntry("ai.service.retry-max-attempts", "${AI_SERVICE_RETRY_MAX_ATTEMPTS:2}");

		contextRunner
			.withPropertyValues("ai.service.retry-max-attempts=2")
			.run(context -> {
				assertThat(context).hasNotFailed();
				assertThat(context.getBean(AiServiceProperties.class).retryMaxAttempts()).isEqualTo(2);
			});
	}

	@Test
	void configuredThreeTotalAttemptsFailsBindingValidation() {
		contextRunner
			.withPropertyValues("ai.service.retry-max-attempts=3")
			.run(context -> {
				assertThat(context).hasFailed();
				assertThat(context.getStartupFailure())
					.hasMessageContaining("ai.service")
					.hasRootCauseInstanceOf(BindValidationException.class);
			});
	}

	@Configuration(proxyBeanMethods = false)
	@EnableConfigurationProperties(AiServiceProperties.class)
	static class PropertiesConfiguration {
	}
}
