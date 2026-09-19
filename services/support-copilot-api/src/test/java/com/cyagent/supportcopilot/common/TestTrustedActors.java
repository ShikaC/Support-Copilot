package com.cyagent.supportcopilot.common;

import java.util.Arrays;

import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

public final class TestTrustedActors {

	private TestTrustedActors() {
	}

	public static void authenticate(String subject, String... roles) {
		authenticateWithScopes(subject, java.util.List.of(), roles);
	}

	public static void authenticateWithScopes(String subject, java.util.List<String> scopes, String... roles) {
		var jwt = Jwt.withTokenValue("synthetic-trusted-test-jwt")
			.header("alg", "none")
			.subject(subject)
			.claim("support_scopes", scopes)
			.build();
		var authorities = Arrays.stream(roles)
			.map(role -> new SimpleGrantedAuthority("ROLE_" + role))
			.toList();
		SecurityContextHolder.getContext().setAuthentication(new JwtAuthenticationToken(jwt, authorities));
	}

	public static void clear() {
		SecurityContextHolder.clearContext();
	}
}
