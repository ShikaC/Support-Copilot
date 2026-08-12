package com.cyagent.supportcopilot.analysis;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;
import java.time.Instant;
import java.util.UUID;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import com.cyagent.supportcopilot.ticket.Ticket;
import com.cyagent.supportcopilot.ticket.TicketRepository;

@SpringBootTest
class AnalysisPersistenceServiceTests {

	@Autowired
	private AnalysisPersistenceService analysisPersistenceService;

	@Autowired
	private AnalysisRunRepository analysisRunRepository;

	@Autowired
	private TicketRepository ticketRepository;

	@Autowired
	private MockAnalysisFactory mockAnalysisFactory;

	private String ticketId;

	@AfterEach
	void cleanUp() {
		if (ticketId != null) {
			analysisRunRepository.findByTicketIdOrderByCreatedAtDesc(ticketId)
				.forEach(analysisRunRepository::delete);
			ticketRepository.deleteById(ticketId);
		}
	}

	@Test
	void savesAnalysisAndTicketTogetherWithSourceVersion() {
		var ticket = saveTicket();
		var sourceVersion = ticket.getVersion();
		var response = mockAnalysisFactory.create(ticket, "mock");

		analysisPersistenceService.persist(ticket.getId(), sourceVersion, response);

		var savedRun = analysisRunRepository.findById(response.id()).orElseThrow();
		var savedTicket = ticketRepository.findById(ticket.getId()).orElseThrow();
		assertThat(savedRun.getSourceTicketVersion()).isEqualTo(sourceVersion);
		assertThat(savedTicket.getVersion()).isEqualTo(sourceVersion + 1);
		assertThat(savedTicket.getStatus()).isEqualTo("NEEDS_ESCALATION");
	}

	@Test
	void rejectsAnalysisWhenTicketVersionHasChanged() {
		// 模拟 AI 分析期间，另一名客服先提交了工单状态变更。
		var ticket = saveTicket();
		var sourceVersion = ticket.getVersion();
		var response = mockAnalysisFactory.create(ticket, "mock");
		ticket.setStatus("IN_PROGRESS");
		var currentTicket = ticketRepository.saveAndFlush(ticket);

		// 仍提交 AI 基于旧版本生成的结果，持久化 Service 应拒绝它。
		assertThatThrownBy(() -> analysisPersistenceService.persist(ticket.getId(), sourceVersion, response))
			.isInstanceOf(TicketVersionConflictException.class)
			.satisfies(exception -> {
				var conflict = (TicketVersionConflictException) exception;
				assertThat(conflict.getExpectedVersion()).isEqualTo(sourceVersion);
				assertThat(conflict.getCurrentVersion()).isEqualTo(currentTicket.getVersion());
				});

		// 版本冲突必须拒绝旧分析，数据库不能留下新的 AnalysisRun。
		assertThat(analysisRunRepository.existsById(response.id())).isFalse();
		// 最新工单保持其他操作提交后的状态，旧分析不能覆盖它。
		assertThat(ticketRepository.findById(ticket.getId()).orElseThrow().getStatus()).isEqualTo("IN_PROGRESS");
	}

	@Test
	void rollsBackTicketUpdateWhenAnalysisRunCannotBeSaved() {
		var ticket = saveTicket();
		var sourceVersion = ticket.getVersion();
		var validResponse = mockAnalysisFactory.create(ticket, "mock");
		// 用缺少状态的响应制造保存失败，验证 Ticket 更新会和分析记录一起回滚。
		var invalidResponse = new AnalysisResponse(
			validResponse.id(),
			validResponse.traceId(),
			null,
			validResponse.mode(),
			validResponse.modelName(),
			validResponse.promptVersion(),
			validResponse.classification(),
			validResponse.workflowSteps(),
			validResponse.retrieval(),
			validResponse.suggestedReply(),
			validResponse.decision(),
			validResponse.usage(),
			validResponse.createdAt()
		);

		assertThatThrownBy(() -> analysisPersistenceService.persist(ticket.getId(), sourceVersion, invalidResponse))
			.isInstanceOf(RuntimeException.class);

		var unchangedTicket = ticketRepository.findById(ticket.getId()).orElseThrow();
		assertThat(analysisRunRepository.existsById(invalidResponse.id())).isFalse();
		assertThat(unchangedTicket.getVersion()).isEqualTo(sourceVersion);
		assertThat(unchangedTicket.getStatus()).isEqualTo("NEW");
	}

	private Ticket saveTicket() {
		var now = Instant.now();
		var ticket = new Ticket();
		ticketId = "ticket-test-" + UUID.randomUUID();
		ticket.setId(ticketId);
		ticket.setTicketNo("SC-TEST-" + UUID.randomUUID().toString().substring(0, 8));
		ticket.setChannel("EMAIL");
		ticket.setCustomerName("测试客户");
		ticket.setCustomerCompany("测试公司");
		ticket.setCustomerTier("STANDARD");
		ticket.setSubject("重复扣款测试");
		ticket.setDescription("用于验证分析保存事务和版本冲突。");
		ticket.setLanguage("zh-CN");
		ticket.setCategory("BILLING");
		ticket.setPriority("HIGH");
		ticket.setStatus("NEW");
		ticket.setSlaDeadline(now.plus(Duration.ofHours(8)));
		ticket.setCreatedAt(now);
		ticket.setUpdatedAt(now);
		return ticketRepository.saveAndFlush(ticket);
	}
}
