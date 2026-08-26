package com.cyagent.supportcopilot.config;

import java.nio.charset.StandardCharsets;
import java.util.Collection;
import java.util.List;

import javax.crypto.spec.SecretKeySpec;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.core.convert.converter.Converter;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtDecoders;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationConverter;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
public class SecurityConfig {

	@Bean
	@Profile("demo")
	SecurityFilterChain demoSecurityFilterChain(HttpSecurity http) throws Exception {
		return http
			.csrf(AbstractHttpConfigurer::disable)
			.cors(Customizer.withDefaults())
			.authorizeHttpRequests(authorize -> authorize
				.requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
				.requestMatchers(
					"/actuator/health",
					"/actuator/health/liveness",
					"/actuator/health/readiness",
					"/api/**",
					"/h2-console/**"
				).permitAll()
				.anyRequest().denyAll())
			.headers(headers -> headers.frameOptions(frameOptions -> frameOptions.sameOrigin()))
			.build();
	}

	@Bean
	@Profile({"test", "local", "pilot"})
	SecurityFilterChain securedSecurityFilterChain(
		HttpSecurity http,
		SecurityErrorHandlers errorHandlers
	) throws Exception {
		return http
			.csrf(AbstractHttpConfigurer::disable)
			.cors(Customizer.withDefaults())
			.authorizeHttpRequests(authorize -> authorize
				.requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
				.requestMatchers(
					"/actuator/health",
					"/actuator/health/liveness",
					"/actuator/health/readiness"
				).permitAll()
				.requestMatchers("/api/audit-events/**")
					.hasAnyRole("SUPPORT_REVIEWER", "SUPPORT_ADMIN")
				.requestMatchers(HttpMethod.POST, "/api/knowledge/releases", "/api/knowledge/releases/**")
					.hasAnyRole("SUPPORT_REVIEWER", "SUPPORT_ADMIN")
				.requestMatchers("/api/tickets/*/analyses/*/reviews/**")
					.hasAnyRole("SUPPORT_REVIEWER", "SUPPORT_ADMIN")
				.requestMatchers("/api/tickets/**", "/api/knowledge/**", "/api/metrics/**")
					.hasAnyRole("SUPPORT_AGENT", "SUPPORT_REVIEWER", "SUPPORT_ADMIN")
				.requestMatchers("/actuator/**").hasRole("SUPPORT_ADMIN")
				.anyRequest().denyAll())
			.oauth2ResourceServer(resourceServer -> resourceServer
				.jwt(jwt -> jwt.jwtAuthenticationConverter(jwtAuthenticationConverter()))
				.authenticationEntryPoint(errorHandlers.authenticationEntryPoint()))
			.exceptionHandling(exceptions -> exceptions
				.authenticationEntryPoint(errorHandlers.authenticationEntryPoint())
				.accessDeniedHandler(errorHandlers.accessDeniedHandler()))
			.build();
	}

	@Bean
	@Profile("test")
	JwtDecoder testJwtDecoder(
		@Value("${support-copilot.security.test-jwt-secret}") String testJwtSecret
	) {
		var key = new SecretKeySpec(testJwtSecret.getBytes(StandardCharsets.UTF_8), "HmacSHA256");
		return NimbusJwtDecoder.withSecretKey(key)
			.macAlgorithm(MacAlgorithm.HS256)
			.build();
	}

	@Bean
	@Profile({"local", "pilot"})
	JwtDecoder externalJwtDecoder(
		@Value("${spring.security.oauth2.resourceserver.jwt.issuer-uri:}") String issuerUri,
		@Value("${spring.security.oauth2.resourceserver.jwt.jwk-set-uri:}") String jwkSetUri
	) {
		if (!jwkSetUri.isBlank()) {
			var decoder = NimbusJwtDecoder.withJwkSetUri(jwkSetUri).build();
			decoder.setJwtValidator(issuerUri.isBlank()
				? JwtValidators.createDefault()
				: JwtValidators.createDefaultWithIssuer(issuerUri));
			return decoder;
		}
		return JwtDecoders.fromIssuerLocation(issuerUri);
	}

	private JwtAuthenticationConverter jwtAuthenticationConverter() {
		var converter = new JwtAuthenticationConverter();
		converter.setJwtGrantedAuthoritiesConverter(roleAuthorities());
		return converter;
	}

	private Converter<Jwt, Collection<GrantedAuthority>> roleAuthorities() {
		return jwt -> {
			var roles = jwt.getClaimAsStringList("roles");
			if (roles == null) {
				return List.of();
			}
			return roles.stream()
				.filter(role -> role.equals("SUPPORT_AGENT")
					|| role.equals("SUPPORT_REVIEWER")
					|| role.equals("SUPPORT_ADMIN"))
				.map(role -> (GrantedAuthority) new SimpleGrantedAuthority("ROLE_" + role))
				.toList();
		};
	}
}
