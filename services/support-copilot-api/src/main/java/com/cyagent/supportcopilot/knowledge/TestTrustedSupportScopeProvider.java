package com.cyagent.supportcopilot.knowledge;

import java.util.List;

import org.springframework.context.annotation.Profile;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Component;

@Component
@Profile("test")
public class TestTrustedSupportScopeProvider implements TrustedSupportScopeProvider {

	@Override
	public List<KnowledgeScope> currentScopes() {
		var authentication = SecurityContextHolder.getContext().getAuthentication();
		if (!(authentication instanceof JwtAuthenticationToken jwt) || !authentication.isAuthenticated()) {
			return List.of();
		}
		var claims = jwt.getToken().getClaimAsStringList("support_scopes");
		return claims == null ? List.of() : JwtTrustedSupportScopeProvider.allowlisted(claims);
	}
}
