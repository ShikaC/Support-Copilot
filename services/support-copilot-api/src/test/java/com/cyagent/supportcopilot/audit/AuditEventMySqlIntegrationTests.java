package com.cyagent.supportcopilot.audit;

import static com.cyagent.supportcopilot.common.MySqlTestSupport.container;
import static com.cyagent.supportcopilot.common.MySqlTestSupport.startContext;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.slf4j.MDC;
import org.springframework.jdbc.core.JdbcTemplate;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.mysql.MySQLContainer;

import com.cyagent.supportcopilot.common.TestTrustedActors;
import com.cyagent.supportcopilot.ticket.TicketDtos.CreateTicketRequest;
import com.cyagent.supportcopilot.ticket.TicketDtos.UpdateTicketRequest;
import com.cyagent.supportcopilot.ticket.TicketDomain.Channel;
import com.cyagent.supportcopilot.ticket.TicketDomain.CustomerTier;
import com.cyagent.supportcopilot.ticket.TicketDomain.Priority;
import com.cyagent.supportcopilot.ticket.TicketRepository;
import com.cyagent.supportcopilot.ticket.TicketService;

@EnabledIfEnvironmentVariable(named = "SUPPORT_COPILOT_RUN_MYSQL_TESTS", matches = "true")
@Testcontainers
class AuditEventMySqlIntegrationTests {

	@Container
	static final MySQLContainer MYSQL = container("support_copilot_audit");

	@Test
	void trustedTicketMutationAndItsSingleAuditEventSurviveApplicationRestart() {
		String ticketId;
		try (var context = startContext(MYSQL)) {
			TestTrustedActors.authenticate("mysql-ticket-agent", "SUPPORT_AGENT");
			MDC.put("traceId", "trace-mysql-ticket-update");
			try {
				var service = context.getBean(TicketService.class);
				var created = service.create(ticketRequest("Committed MySQL audit"));
				ticketId = created.id();
				var updated = service.update(ticketId, new UpdateTicketRequest(
					null, Priority.HIGH, null, null, created.version()
				));
				assertThat(updated.priority()).isEqualTo("HIGH");
				assertThat(updateAuditCount(context.getBean(JdbcTemplate.class), ticketId)).isEqualTo(1);
			} finally {
				TestTrustedActors.clear();
				MDC.remove("traceId");
			}
		}

		try (var restarted = startContext(MYSQL)) {
			assertThat(restarted.getBean(TicketRepository.class).findById(ticketId).orElseThrow().getPriority())
				.isEqualTo("HIGH");
			var jdbc = restarted.getBean(JdbcTemplate.class);
			assertThat(updateAuditCount(jdbc, ticketId)).isEqualTo(1);
			assertThat(jdbc.queryForObject(
				"select actor_subject from audit_events where target_id = ? and action = 'TICKET_UPDATED'",
				String.class,
				ticketId
			)).isEqualTo("mysql-ticket-agent");
		}
	}

	@Test
	void auditInsertFailureRollsBackTicketWithoutAnOrphanEvent() {
		try (var context = startContext(MYSQL)) {
			var tickets = context.getBean(TicketRepository.class);
			var jdbc = context.getBean(JdbcTemplate.class);
			var ticketCount = tickets.count();
			var auditCount = jdbc.queryForObject("select count(*) from audit_events", Long.class);
			TestTrustedActors.authenticate("actor-" + "x".repeat(140), "SUPPORT_AGENT");
			MDC.put("traceId", "trace-mysql-audit-rollback");

			try {
				assertThatThrownBy(() -> context.getBean(TicketService.class)
					.create(ticketRequest("Rolled back MySQL audit")))
					.isInstanceOf(RuntimeException.class);
			} finally {
				TestTrustedActors.clear();
				MDC.remove("traceId");
			}

			assertThat(tickets.count()).isEqualTo(ticketCount);
			assertThat(jdbc.queryForObject("select count(*) from audit_events", Long.class)).isEqualTo(auditCount);
		}
	}

	private CreateTicketRequest ticketRequest(String subject) {
		return new CreateTicketRequest(
			Channel.EMAIL,
			"Synthetic MySQL Customer",
			"Task 15 Verification",
			CustomerTier.STANDARD,
			subject,
			"Synthetic transaction data.",
			"en-US"
		);
	}

	private long updateAuditCount(JdbcTemplate jdbc, String ticketId) {
		return jdbc.queryForObject(
			"select count(*) from audit_events where target_id = ? and action = 'TICKET_UPDATED'",
			Long.class,
			ticketId
		);
	}
}
