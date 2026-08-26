package com.cyagent.supportcopilot.identity;

import java.util.List;

public interface TrustedActorProvider {

	TrustedActor currentActor();

	enum TrustedActorType {
		AUTHENTICATED_JWT,
		UNAUTHENTICATED_DEMO
	}

	enum TrustedRole {
		DEMO,
		SUPPORT_ADMIN,
		SUPPORT_AGENT,
		SUPPORT_REVIEWER
	}

	record TrustedActor(
		String subject,
		TrustedActorType type,
		List<TrustedRole> roles,
		String displayLabel
	) {

		public TrustedActor {
			if (subject == null || subject.isBlank()) {
				throw new IllegalArgumentException("Trusted actor subject must be non-blank.");
			}
			if (type == null) {
				throw new IllegalArgumentException("Trusted actor type is required.");
			}
			roles = roles == null
				? List.of()
				: roles.stream().filter(java.util.Objects::nonNull)
					.distinct().sorted().toList();
			displayLabel = displayLabel == null || displayLabel.isBlank() ? subject : displayLabel;
		}
	}
}
