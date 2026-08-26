package com.cyagent.supportcopilot.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.stream.Stream;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.support.GenericApplicationContext;
import org.springframework.mock.env.MockEnvironment;

import com.cyagent.supportcopilot.SupportCopilotApiApplication;

class RuntimeProfileIntegrationTests {

	private static final String REQUIRED_PROFILE_MESSAGE =
		"Application startup requires exactly one active profile from: demo, test, local, pilot.";
	private static final String INTERNAL_TOKEN = "SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN";
	private static final String JWT_ISSUER = "SUPPORT_COPILOT_JWT_ISSUER_URI";
	private static final String JWT_JWK_SET = "SUPPORT_COPILOT_JWT_JWK_SET_URI";

	@ParameterizedTest(name = "{0}: {1}")
	@MethodSource("invalidSecureProfileSettings")
	void localAndPilotRejectMissingOrBlankSecuritySettingsBeforeContextRefresh(
		String profile,
		String scenario,
		String internalToken,
		String issuerUri,
		String jwkSetUri,
		String expectedVariable
	) {
		var environment = new MockEnvironment();
		environment.setActiveProfiles(profile);
		setProperty(environment, INTERNAL_TOKEN, internalToken);
		setProperty(environment, JWT_ISSUER, issuerUri);
		setProperty(environment, JWT_JWK_SET, jwkSetUri);
		try (var context = new GenericApplicationContext()) {
			context.setEnvironment(environment);

			assertThatThrownBy(() -> new RuntimeProfileApplicationContextInitializer().initialize(context))
				.as("%s must fail before datasource or HTTP beans are created", scenario)
				.isInstanceOf(IllegalStateException.class)
				.hasMessageContaining(expectedVariable);
		}
	}

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

	private static Stream<Arguments> invalidSecureProfileSettings() {
		return Stream.of(
			Arguments.of("local", "missing internal token", null, null, "https://issuer.test/jwks", INTERNAL_TOKEN),
			Arguments.of("pilot", "blank internal token", " ", null, "https://issuer.test/jwks", INTERNAL_TOKEN),
			Arguments.of("local", "missing JWT location", "synthetic-runtime-token", null, null, JWT_ISSUER),
			Arguments.of("pilot", "blank JWT locations", "synthetic-runtime-token", " ", " ", JWT_ISSUER)
		);
	}

	private static void setProperty(MockEnvironment environment, String name, String value) {
		if (value != null) {
			environment.setProperty(name, value);
		}
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
