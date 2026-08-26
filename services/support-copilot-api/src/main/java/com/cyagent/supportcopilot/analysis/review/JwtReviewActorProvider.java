package com.cyagent.supportcopilot.analysis.review;

import org.springframework.context.annotation.Profile;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Component;

import com.cyagent.supportcopilot.analysis.review.ReviewActorProvider.ReviewActor;

@Component
@Profile({"test", "local", "pilot"})
public class JwtReviewActorProvider implements ReviewActorProvider {

	@Override
	public ReviewActor currentActor() {
		var authentication = SecurityContextHolder.getContext().getAuthentication();
		if (!(authentication instanceof JwtAuthenticationToken jwtAuthentication)
			|| !authentication.isAuthenticated()) {
			throw new AccessDeniedException("An authenticated JWT subject is required for review actions.");
		}
		return new ReviewActor("AUTHENTICATED_JWT", jwtAuthentication.getToken().getSubject());
	}
}
