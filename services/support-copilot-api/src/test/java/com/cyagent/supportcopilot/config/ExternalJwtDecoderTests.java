package com.cyagent.supportcopilot.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.oauth2.jwt.JwtValidationException;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import com.sun.net.httpserver.HttpServer;

class ExternalJwtDecoderTests {

	private static final String ISSUER = "https://issuer.test/support-copilot";
	private static final String AUDIENCE = "support-copilot-api";

	private HttpServer jwkServer;

	@AfterEach
	void stopJwkServer() {
		if (jwkServer != null) {
			jwkServer.stop(0);
		}
	}

	@Test
	void directJwkSetDecoderRequiresConfiguredIssuerAndAudience() throws Exception {
		var rsaKey = new RSAKeyGenerator(2048).keyID("direct-jwk-test-key").generate();
		var jwkSetUri = startJwkServer(rsaKey);
		var decoder = new SecurityConfig().externalJwtDecoder(ISSUER, jwkSetUri, AUDIENCE);

		var trusted = decoder.decode(signed(rsaKey, ISSUER, AUDIENCE));

		assertThat(trusted.getSubject()).isEqualTo("direct-jwk-subject");
		assertThatThrownBy(() -> decoder.decode(signed(rsaKey, "https://untrusted-issuer.test", AUDIENCE)))
			.isInstanceOf(JwtValidationException.class);
		assertThatThrownBy(() -> decoder.decode(signed(rsaKey, ISSUER, "another-api")))
			.isInstanceOf(JwtValidationException.class);
	}

	private String startJwkServer(RSAKey rsaKey) throws Exception {
		var response = new JWKSet(rsaKey.toPublicJWK()).toString().getBytes(StandardCharsets.UTF_8);
		jwkServer = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
		jwkServer.createContext("/jwks", exchange -> {
			exchange.getResponseHeaders().add("Content-Type", "application/json");
			exchange.sendResponseHeaders(200, response.length);
			try (var body = exchange.getResponseBody()) {
				body.write(response);
			}
		});
		jwkServer.start();
		return "http://127.0.0.1:" + jwkServer.getAddress().getPort() + "/jwks";
	}

	private String signed(RSAKey rsaKey, String issuer, String audience) throws Exception {
		var now = Instant.now();
		var claims = new JWTClaimsSet.Builder()
			.subject("direct-jwk-subject")
			.issuer(issuer)
			.audience(audience)
			.issueTime(Date.from(now))
			.expirationTime(Date.from(now.plus(Duration.ofMinutes(5))))
			.build();
		var header = new JWSHeader.Builder(JWSAlgorithm.RS256).keyID(rsaKey.getKeyID()).build();
		var jwt = new SignedJWT(header, claims);
		jwt.sign(new RSASSASigner(rsaKey));
		return jwt.serialize();
	}
}
