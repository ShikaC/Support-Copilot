package com.cyagent.supportcopilot.analysis;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;

import org.junit.jupiter.api.Test;

import com.cyagent.supportcopilot.ticket.Ticket;

class MockAnalysisFactoryTests {

	private final MockAnalysisFactory factory = new MockAnalysisFactory();

	@Test
	void billingTicketsRequireEscalationAndReturnEvidence() {
		var response = factory.create(ticket("BILLING", "HIGH"), "mock");

		assertThat(response.decision().escalationRequired()).isTrue();
		assertThat(response.retrieval().hits()).hasSize(2);
		assertThat(response.suggestedReply().citations()).isNotEmpty();
		assertThat(response.mode()).isEqualTo("mock");
	}

	@Test
	void missingRecoveryEvidenceFallsBackToManualReview() {
		var response = factory.create(ticket("DATA_RECOVERY", "MEDIUM"), "mock");

		assertThat(response.mode()).isEqualTo("fallback");
		assertThat(response.status()).isEqualTo("FALLBACK");
		assertThat(response.retrieval().hits()).isEmpty();
		assertThat(response.decision().escalationRequired()).isTrue();
	}

	@Test
	void explicitFallbackIsNotReportedAsSuccessfulAnalysis() {
		var response = factory.create(ticket("SUBSCRIPTION", "LOW"), "fallback");

		assertThat(response.mode()).isEqualTo("fallback");
		assertThat(response.status()).isEqualTo("FALLBACK");
		assertThat(response.classification().confidence()).isLessThanOrEqualTo(0.5);
		assertThat(response.suggestedReply().warnings()).contains("AI 服务不可用，本次为降级结果，必须人工复核。");
		assertThat(response.decision().escalationRequired()).isTrue();
	}

	private Ticket ticket(String category, String priority) {
		var ticket = new Ticket();
		ticket.setId("ticket-test");
		ticket.setTicketNo("SC-TEST");
		ticket.setSubject("测试工单");
		ticket.setDescription("用于验证分析降级逻辑");
		ticket.setLanguage("zh-CN");
		ticket.setCustomerTier("STANDARD");
		ticket.setCategory(category);
		ticket.setPriority(priority);
		ticket.setCreatedAt(Instant.now());
		return ticket;
	}
}
