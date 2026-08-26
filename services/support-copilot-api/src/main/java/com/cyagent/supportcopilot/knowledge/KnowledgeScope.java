package com.cyagent.supportcopilot.knowledge;

import java.util.List;

public enum KnowledgeScope {
	GENERAL,
	BILLING,
	ACCOUNT,
	PRIVACY,
	TECHNICAL;

	public static List<KnowledgeScope> canonicalize(List<String> values) {
		if (values == null) {
			throw KnowledgeReleaseException.invalidScope();
		}
		try {
			var requested = values.stream().map(KnowledgeScope::valueOf).collect(java.util.stream.Collectors.toSet());
			return java.util.Arrays.stream(values())
				.filter(requested::contains)
				.toList();
		} catch (NullPointerException | IllegalArgumentException exception) {
			throw KnowledgeReleaseException.invalidScope();
		}
	}

	public static List<String> names(List<KnowledgeScope> scopes) {
		return scopes.stream().map(Enum::name).toList();
	}
}
