package com.cyagent.supportcopilot.analysis;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;

import org.junit.jupiter.api.Test;

import com.cyagent.supportcopilot.ticket.Ticket;

class MockAnalysisFactoryTests {

	private final MockAnalysisFactory factory = new MockAnalysisFactory();

	@Test
	void billingTicketsRequireEscalationAndReturnEvidence() {
		// Given/When: a billing ticket has usable local evidence.
		var response = factory.createMock(ticket("BILLING", "HIGH"));

		// Then: a successful result has no fallback reason.
		assertThat(response.decision().escalationRequired()).isTrue();
		assertThat(response.retrieval().hits()).hasSize(2);
		assertThat(response.suggestedReply().citations()).isNotEmpty();
		assertThat(response.mode()).isEqualTo("mock");
		assertThat(response.fallbackReason()).isNull();
	}

	@Test
	void missingRecoveryEvidenceFallsBackToManualReview() {
		// Given/When: no knowledge evidence covers the recovery request.
		var response = factory.createMock(ticket("DATA_RECOVERY", "MEDIUM"));

		// Then: the result names evidence absence as its fallback reason.
		assertThat(response.mode()).isEqualTo("fallback");
		assertThat(response.status()).isEqualTo("FALLBACK");
		assertThat(response.fallbackReason()).isEqualTo(FallbackReason.INSUFFICIENT_EVIDENCE);
		assertThat(response.retrieval().hits()).isEmpty();
		assertThat(response.decision().escalationRequired()).isTrue();
	}

	@Test
	void explicitFallbackIsNotReportedAsSuccessfulAnalysis() {
		// Given/When: Java cannot reach the Python AI service.
		var response = factory.createFallback(
			ticket("SUBSCRIPTION", "LOW"),
			"trace-service-unavailable",
			FallbackReason.AI_SERVICE_UNAVAILABLE
		);

		// Then: the result preserves the named infrastructure reason.
		assertThat(response.mode()).isEqualTo("fallback");
		assertThat(response.status()).isEqualTo("FALLBACK");
		assertThat(response.fallbackReason()).isEqualTo(FallbackReason.AI_SERVICE_UNAVAILABLE);
		assertThat(response.classification().confidence()).isLessThanOrEqualTo(0.5);
		assertThat(response.retrieval().hits()).isEmpty();
		assertThat(response.suggestedReply().citations()).isEmpty();
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
