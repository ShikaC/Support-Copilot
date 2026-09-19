package com.cyagent.supportcopilot.analysis.review;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

import com.cyagent.supportcopilot.ticket.Ticket;

final class AnalysisReviewTestFixture {

	private AnalysisReviewTestFixture() {
	}

	static void authenticateReviewer() {
		var jwt = Jwt.withTokenValue("synthetic-reviewer-jwt")
			.header("alg", "none")
			.subject("service-test-reviewer")
			.claim("support_scopes", List.of("BILLING"))
			.build();
		var authentication = new JwtAuthenticationToken(
			jwt,
			List.of(new SimpleGrantedAuthority("ROLE_SUPPORT_REVIEWER"))
		);
		SecurityContextHolder.getContext().setAuthentication(authentication);
	}

	static void clearAuthentication() {
		SecurityContextHolder.clearContext();
	}

	static Ticket ticket() {
		var now = Instant.now();
		var ticket = new Ticket();
		ticket.setId("ticket-" + UUID.randomUUID());
		ticket.setTicketNo("SC-REVIEW-" + UUID.randomUUID().toString().substring(0, 8));
		ticket.setChannel("EMAIL");
		ticket.setCustomerName("审核测试客户");
		ticket.setCustomerCompany("审核测试公司");
		ticket.setCustomerTier("STANDARD");
		ticket.setSubject("回复审核测试");
		ticket.setDescription("用于验证 AI 建议经过人工审核后才形成业务记录。");
		ticket.setLanguage("zh-CN");
		ticket.setCategory("BILLING");
		ticket.setPriority("HIGH");
		ticket.setStatus("NEW");
		ticket.setSlaDeadline(now.plus(Duration.ofHours(8)));
		ticket.setCreatedAt(now);
		ticket.setUpdatedAt(now);
		return ticket;
	}
}
