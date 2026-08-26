package com.cyagent.supportcopilot.identity;

import org.springframework.context.annotation.Profile;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Component;

import com.cyagent.supportcopilot.identity.TrustedActorProvider.TrustedActorType;
import com.cyagent.supportcopilot.identity.TrustedActorProvider.TrustedRole;

@Component
@Profile({"test", "local", "pilot"})
public class JwtTrustedActorProvider implements TrustedActorProvider {

	@Override
	public TrustedActor currentActor() {
		var authentication = SecurityContextHolder.getContext().getAuthentication();
		if (!(authentication instanceof JwtAuthenticationToken jwtAuthentication)
			|| !authentication.isAuthenticated()) {
			throw new AccessDeniedException("An authenticated JWT subject is required for this action.");
		}
		var subject = jwtAuthentication.getToken().getSubject();
		if (subject == null || subject.isBlank()) {
			throw new AccessDeniedException("A non-blank JWT subject is required for this action.");
		}
		var roles = authentication.getAuthorities().stream()
			.map(authority -> authority.getAuthority())
			.filter(authority -> authority.startsWith("ROLE_"))
			.map(authority -> authority.substring("ROLE_".length()))
			.filter(role -> role.equals("SUPPORT_AGENT")
				|| role.equals("SUPPORT_REVIEWER")
				|| role.equals("SUPPORT_ADMIN"))
			.map(TrustedRole::valueOf)
			.toList();
		return new TrustedActor(subject, TrustedActorType.AUTHENTICATED_JWT, roles, subject);
	}
}
