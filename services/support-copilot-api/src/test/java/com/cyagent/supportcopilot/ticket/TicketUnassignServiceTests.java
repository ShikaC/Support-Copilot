package com.cyagent.supportcopilot.ticket;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;
import java.time.Instant;
import java.util.UUID;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import com.cyagent.supportcopilot.analysis.TicketVersionConflictException;

@SpringBootTest
class TicketUnassignServiceTests {

	@Autowired
	private TicketService ticketService;

	@Autowired
	private TicketRepository ticketRepository;

	private String ticketId;

	@AfterEach
	void cleanUp() {
		if (ticketId != null) {
			ticketRepository.deleteById(ticketId);
		}
	}

	@Test
	void clearsAssigneeAndIncrementsVersion() {
		var ticket = saveTicket("IN_PROGRESS", "周岚");

		var updated = ticketService.unassign(ticket.getId(), ticket.getVersion());

		assertThat(updated.assigneeName()).isNull();
		assertThat(updated.version()).isEqualTo(ticket.getVersion() + 1);
		assertThat(ticketRepository.findById(ticket.getId()).orElseThrow().getAssigneeName()).isNull();
	}

	@Test
	void repeatedUnassignIsIdempotent() {
		var ticket = saveTicket("IN_PROGRESS", "周岚");
		var first = ticketService.unassign(ticket.getId(), ticket.getVersion());

		var second = ticketService.unassign(ticket.getId(), first.version());

		assertThat(second.assigneeName()).isNull();
		assertThat(second.version()).isEqualTo(first.version());
	}

	@Test
	void rejectsOldVersionWithoutClearingNewAssignee() {
		var ticket = saveTicket("IN_PROGRESS", "周岚");
		var expectedVersion = ticket.getVersion();
		ticket.setAssigneeName("陈屿");
		var changed = ticketRepository.saveAndFlush(ticket);

		assertThatThrownBy(() -> ticketService.unassign(ticket.getId(), expectedVersion))
			.isInstanceOf(TicketVersionConflictException.class);
		assertThat(ticketRepository.findById(ticket.getId()).orElseThrow().getAssigneeName())
			.isEqualTo("陈屿");
		assertThat(changed.getVersion()).isGreaterThan(expectedVersion);
	}

	@Test
	void rejectsUnassignForTerminalTicket() {
		var ticket = saveTicket("CLOSED", "周岚");

		assertThatThrownBy(() -> ticketService.unassign(ticket.getId(), ticket.getVersion()))
			.isInstanceOf(TicketStateConflictException.class);
		assertThat(ticketRepository.findById(ticket.getId()).orElseThrow().getAssigneeName())
			.isEqualTo("周岚");
	}

	private Ticket saveTicket(String status, String assigneeName) {
		var now = Instant.now();
		var ticket = new Ticket();
		ticketId = "ticket-test-" + UUID.randomUUID();
		ticket.setId(ticketId);
		ticket.setTicketNo("SC-TEST-" + UUID.randomUUID().toString().substring(0, 8));
		ticket.setChannel("EMAIL");
		ticket.setCustomerName("测试客户");
		ticket.setCustomerCompany("测试公司");
		ticket.setCustomerTier("STANDARD");
		ticket.setSubject("取消负责人测试");
		ticket.setDescription("用于验证负责人命令和版本保护。");
		ticket.setLanguage("zh-CN");
		ticket.setCategory("BILLING");
		ticket.setPriority("HIGH");
		ticket.setStatus(status);
		ticket.setAssigneeName(assigneeName);
		ticket.setSlaDeadline(now.plus(Duration.ofHours(8)));
		ticket.setCreatedAt(now);
		ticket.setUpdatedAt(now);
		return ticketRepository.saveAndFlush(ticket);
	}
}
