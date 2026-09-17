package com.cyagent.supportcopilot.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.stream.Stream;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.support.GenericApplicationContext;
import org.springframework.mock.env.MockEnvironment;

import com.cyagent.supportcopilot.SupportCopilotApiApplication;

class RuntimeProfileIntegrationTests {

	private static final String REQUIRED_PROFILE_MESSAGE =
		"Application startup requires exactly one active profile from: demo, test, local, pilot.";
	private static final String INTERNAL_TOKEN = "SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN";
	private static final String JWT_ISSUER = "SUPPORT_COPILOT_JWT_ISSUER_URI";
	private static final String JWT_JWK_SET = "SUPPORT_COPILOT_JWT_JWK_SET_URI";
	private static final String JWT_AUDIENCE = "SUPPORT_COPILOT_JWT_AUDIENCE";

	@ParameterizedTest(name = "{0}: {1}")
	@MethodSource("invalidSecureProfileSettings")
	void localAndPilotRejectMissingOrBlankSecuritySettingsBeforeContextRefresh(
		String profile,
		String scenario,
		String internalToken,
		String issuerUri,
		String jwkSetUri,
		String audience,
		String expectedVariable
	) {
		var environment = new MockEnvironment();
		environment.setActiveProfiles(profile);
		setProperty(environment, INTERNAL_TOKEN, internalToken);
		setProperty(environment, JWT_ISSUER, issuerUri);
		setProperty(environment, JWT_JWK_SET, jwkSetUri);
		setProperty(environment, JWT_AUDIENCE, audience);
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

	@Test
	void demoDefaultsToAnExplicitLoopbackListener() {
		try (var context = demoContext()) {
			assertThat(context.getEnvironment().getProperty("server.address")).isEqualTo("127.0.0.1");
		}
	}

	@ParameterizedTest
	@ValueSource(strings = { "127.0.0.1", "::1", "[::1]", "0:0:0:0:0:0:0:1", "localhost" })
	void demoAcceptsOnlySupportedLoopbackAddresses(String address) {
		try (var context = demoContext("--server.address=" + address)) {
			assertThat(context.isActive()).isTrue();
		}
	}

	@ParameterizedTest
	@ValueSource(strings = { "0.0.0.0", "::", "[::]", "192.0.2.10", "example.com", "" })
	void demoRejectsWildcardExternalAndBlankListenerAddressesBeforeContextRefresh(String address) {
		assertThatThrownBy(() -> demoContext("--server.address=" + address))
			.isInstanceOf(IllegalStateException.class)
			.hasMessageContaining("demo").hasMessageContaining("server.address");
	}

	@Test
	void demoRejectsAnEnvironmentWithoutAnEffectiveListenerAddress() {
		var environment = new MockEnvironment();
		environment.setActiveProfiles("demo");
		try (var context = new GenericApplicationContext()) {
			context.setEnvironment(environment);
			assertThatThrownBy(() -> new RuntimeProfileApplicationContextInitializer().initialize(context))
				.isInstanceOf(IllegalStateException.class).hasMessageContaining("server.address");
		}
	}

	@Test
	void authenticatedPilotAndTestProfilesRetainTheirListenerPolicy() {
		for (var profile : new String[] { "pilot", "test" }) {
			var environment = new MockEnvironment().withProperty("server.address", "0.0.0.0")
				.withProperty(INTERNAL_TOKEN, "synthetic-runtime-token")
				.withProperty(JWT_ISSUER, "https://issuer.test").withProperty(JWT_AUDIENCE, "support-copilot-api");
			environment.setActiveProfiles(profile);
			try (var context = new GenericApplicationContext()) {
				context.setEnvironment(environment);
				new RuntimeProfileApplicationContextInitializer().initialize(context);
			}
		}
	}

	private static ConfigurableApplicationContext demoContext(String... listenerArguments) {
		var arguments = Stream.concat(Stream.of("--spring.profiles.active=demo"), Stream.of(listenerArguments))
			.toArray(String[]::new);
		return new SpringApplicationBuilder(RuntimeProfileProbe.class).web(WebApplicationType.NONE).run(arguments);
	}

	@TestConfiguration(proxyBeanMethods = false)
	static class RuntimeProfileProbe {}

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
			Arguments.of("local", "missing internal token", null, "https://issuer.test", null,
				"support-copilot-api", INTERNAL_TOKEN),
			Arguments.of("pilot", "blank internal token", " ", "https://issuer.test", null,
				"support-copilot-api", INTERNAL_TOKEN),
			Arguments.of("local", "missing issuer with JWK configured", "synthetic-runtime-token", null,
				"https://issuer.test/jwks", "support-copilot-api", JWT_ISSUER),
			Arguments.of("pilot", "blank issuer with JWK configured", "synthetic-runtime-token", " ",
				"https://issuer.test/jwks", "support-copilot-api", JWT_ISSUER),
			Arguments.of("local", "missing audience", "synthetic-runtime-token", "https://issuer.test",
				null, null, JWT_AUDIENCE),
			Arguments.of("pilot", "blank audience", "synthetic-runtime-token", "https://issuer.test",
				null, " ", JWT_AUDIENCE)
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
