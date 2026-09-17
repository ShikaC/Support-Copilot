package com.cyagent.supportcopilot.config;

import java.util.List;
import java.util.Locale;
import java.util.Set;

import org.springframework.context.ApplicationContextInitializer;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.core.Ordered;

public final class RuntimeProfileApplicationContextInitializer
	implements ApplicationContextInitializer<ConfigurableApplicationContext>, Ordered {

	private static final Set<String> ALLOWED_PROFILES = Set.of("demo", "test", "local", "pilot");
	private static final Set<String> DEMO_LOOPBACK_ADDRESSES = Set.of(
		"127.0.0.1", "::1", "[::1]", "0:0:0:0:0:0:0:1", "[0:0:0:0:0:0:0:1]", "localhost"
	);
	private static final String REQUIRED_PROFILE_MESSAGE =
		"Application startup requires exactly one active profile from: demo, test, local, pilot.";
	private static final String INTERNAL_TOKEN = "SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN";
	private static final String JWT_ISSUER = "SUPPORT_COPILOT_JWT_ISSUER_URI";
	private static final String JWT_AUDIENCE = "SUPPORT_COPILOT_JWT_AUDIENCE";

	@Override
	public void initialize(ConfigurableApplicationContext applicationContext) {
		var activeProfiles = List.of(applicationContext.getEnvironment().getActiveProfiles());
		if (activeProfiles.size() != 1 || !ALLOWED_PROFILES.contains(activeProfiles.getFirst())) {
			var activeDescription = activeProfiles.isEmpty() ? "none" : String.join(", ", activeProfiles);
			throw new IllegalStateException(REQUIRED_PROFILE_MESSAGE
				+ " Active profiles: " + activeDescription + ".");
		}
		var profile = activeProfiles.getFirst();
		if (profile.equals("demo")) {
			var address = applicationContext.getEnvironment().getProperty("server.address", "").trim().toLowerCase(Locale.ROOT);
			if (!DEMO_LOOPBACK_ADDRESSES.contains(address)) {
				throw new IllegalStateException("The anonymous demo profile requires a loopback server.address (127.0.0.1, ::1, or localhost).");
			}
		}
		if (profile.equals("local") || profile.equals("pilot")) {
			requireNonBlank(applicationContext, INTERNAL_TOKEN);
			requireNonBlank(applicationContext, JWT_ISSUER);
			requireNonBlank(applicationContext, JWT_AUDIENCE);
		}
	}

	private void requireNonBlank(ConfigurableApplicationContext context, String propertyName) {
		if (isBlank(context.getEnvironment().getProperty(propertyName))) {
			throw new IllegalStateException(propertyName + " must be configured with a non-blank value.");
		}
	}

	private boolean isBlank(String value) {
		return value == null || value.isBlank();
	}

	@Override
	public int getOrder() {
		return Ordered.HIGHEST_PRECEDENCE;
	}
}
