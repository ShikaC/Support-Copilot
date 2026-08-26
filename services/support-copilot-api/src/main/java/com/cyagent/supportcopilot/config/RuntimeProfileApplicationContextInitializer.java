package com.cyagent.supportcopilot.config;

import java.util.List;
import java.util.Set;

import org.springframework.context.ApplicationContextInitializer;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.core.Ordered;

public final class RuntimeProfileApplicationContextInitializer
	implements ApplicationContextInitializer<ConfigurableApplicationContext>, Ordered {

	private static final Set<String> ALLOWED_PROFILES = Set.of("demo", "test", "local", "pilot");
	private static final String REQUIRED_PROFILE_MESSAGE =
		"Application startup requires exactly one active profile from: demo, test, local, pilot.";

	@Override
	public void initialize(ConfigurableApplicationContext applicationContext) {
		var activeProfiles = List.of(applicationContext.getEnvironment().getActiveProfiles());
		if (activeProfiles.size() != 1 || !ALLOWED_PROFILES.contains(activeProfiles.getFirst())) {
			var activeDescription = activeProfiles.isEmpty() ? "none" : String.join(", ", activeProfiles);
			throw new IllegalStateException(REQUIRED_PROFILE_MESSAGE
				+ " Active profiles: " + activeDescription + ".");
		}
	}

	@Override
	public int getOrder() {
		return Ordered.HIGHEST_PRECEDENCE;
	}
}
