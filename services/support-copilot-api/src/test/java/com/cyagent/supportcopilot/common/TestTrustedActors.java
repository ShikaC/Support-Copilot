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
		var jwt = Jwt.withTokenValue("synthetic-trusted-test-jwt")
			.header("alg", "none")
			.subject(subject)
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
