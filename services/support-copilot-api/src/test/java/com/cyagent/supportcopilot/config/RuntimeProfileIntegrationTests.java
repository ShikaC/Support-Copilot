package com.cyagent.supportcopilot.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.stream.Stream;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;

import com.cyagent.supportcopilot.SupportCopilotApiApplication;

class RuntimeProfileIntegrationTests {

	private static final String REQUIRED_PROFILE_MESSAGE =
		"Application startup requires exactly one active profile from: demo, test, local, pilot.";

	@ParameterizedTest(name = "{0}")
	@MethodSource("invalidRuntimeProfiles")
	void rejectsMissingUnsupportedOrAmbiguousRuntimeProfiles(
		String scenario,
		String activeProfiles,
		String expectedActiveProfiles
	) {
		var failure = startupFailure(activeProfiles);

		assertThat(failure)
			.as("%s must fail before the application can be used", scenario)
			.isNotNull();
		assertThat(rootCause(failure))
			.isInstanceOf(IllegalStateException.class)
			.hasMessage(REQUIRED_PROFILE_MESSAGE + " Active profiles: " + expectedActiveProfiles + ".");
	}

	private static Stream<Arguments> invalidRuntimeProfiles() {
		return Stream.of(
			Arguments.of("no active profile", null, "none"),
			Arguments.of("explicit default profile", "default", "default"),
			Arguments.of("unsupported profile", "staging", "staging"),
			Arguments.of("multiple runtime profiles", "demo,test", "demo, test")
		);
	}

	private static Throwable startupFailure(String activeProfiles) {
		ConfigurableApplicationContext context = null;
		try {
			var application = new SpringApplicationBuilder(SupportCopilotApiApplication.class)
				.web(WebApplicationType.NONE);
			context = activeProfiles == null
				? application.run()
				: application.run("--spring.profiles.active=" + activeProfiles);
			return null;
		}
		catch (Throwable failure) {
			return failure;
		}
		finally {
			if (context != null) {
				context.close();
			}
		}
	}

	private static Throwable rootCause(Throwable failure) {
		var result = failure;
		while (result.getCause() != null) {
			result = result.getCause();
		}
		return result;
	}
}
