package com.cyagent.supportcopilot.common;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.List;
import java.util.Map;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;

public final class SyntheticJwt {
	public static final String TRUSTED_ISSUER = "https://issuer.test/support-copilot";
	public static final String EXPECTED_AUDIENCE = "support-copilot-api";

	private SyntheticJwt() {
	}

	public static String signed(String secret, String role, String subject) throws Exception {
		return signed(secret, role, subject, Map.of());
	}

	public static String signed(
		String secret,
		String role,
		String subject,
		Map<String, Object> additionalClaims
	) throws Exception {
		var claims = claims(role, subject)
			.issuer(TRUSTED_ISSUER)
			.audience(EXPECTED_AUDIENCE);
		additionalClaims.forEach(claims::claim);
		return sign(secret, claims);
	}

	public static String signedWithoutAudience(String secret, String role, String subject) throws Exception {
		return sign(secret, claims(role, subject).issuer(TRUSTED_ISSUER));
	}

	public static String signedWithoutIssuer(String secret, String role, String subject) throws Exception {
		return sign(secret, claims(role, subject).audience(EXPECTED_AUDIENCE));
	}

	private static JWTClaimsSet.Builder claims(String role, String subject) {
		var now = Instant.now();
		var claims = new JWTClaimsSet.Builder()
			.issueTime(Date.from(now))
			.expirationTime(Date.from(now.plus(Duration.ofMinutes(5))))
			.claim("roles", List.of(role));
		if (subject != null) {
			claims.subject(subject);
		}
		return claims;
	}

	private static String sign(String secret, JWTClaimsSet.Builder claims) throws Exception {
		var jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), claims.build());
		jwt.sign(new MACSigner(secret.getBytes(StandardCharsets.UTF_8)));
		return jwt.serialize();
	}
}
