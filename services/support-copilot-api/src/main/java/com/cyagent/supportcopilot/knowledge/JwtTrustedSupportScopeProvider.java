package com.cyagent.supportcopilot.knowledge;

import java.util.List;

import org.springframework.context.annotation.Profile;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Component;

@Component
@Profile({"local", "pilot"})
public class JwtTrustedSupportScopeProvider implements TrustedSupportScopeProvider {

	@Override
	public List<KnowledgeScope> currentScopes() {
		var authentication = SecurityContextHolder.getContext().getAuthentication();
		if (!(authentication instanceof JwtAuthenticationToken jwt) || !authentication.isAuthenticated()) {
			return List.of();
		}
		var claims = jwt.getToken().getClaimAsStringList("support_scopes");
		return claims == null ? List.of() : allowlisted(claims);
	}

	static List<KnowledgeScope> allowlisted(List<String> claims) {
		var claimed = claims.stream()
			.filter(java.util.Objects::nonNull)
			.filter(value -> java.util.Arrays.stream(KnowledgeScope.values()).anyMatch(scope -> scope.name().equals(value)))
			.collect(java.util.stream.Collectors.toSet());
		return java.util.Arrays.stream(KnowledgeScope.values())
			.filter(scope -> claimed.contains(scope.name()))
			.toList();
	}
}
