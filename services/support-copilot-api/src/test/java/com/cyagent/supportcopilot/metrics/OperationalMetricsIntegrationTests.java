package com.cyagent.supportcopilot.metrics;

import static org.assertj.core.api.Assertions.assertThat;
import java.time.Instant;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;
import com.cyagent.supportcopilot.common.TestTrustedActors;
import com.cyagent.supportcopilot.ticket.*;

@SpringBootTest
@ActiveProfiles("test")
@Transactional
class OperationalMetricsIntegrationTests {
    @Autowired MetricsService metrics;
    @Autowired TicketService tickets;
    @Autowired TicketRepository repository;
    @Autowired jakarta.persistence.EntityManager database;
    @Autowired OperationalMetrics operational;

    @Test
    void slaRiskUsesDeadlinesAndExcludesTerminalTicketsInsteadOfCountingPriority() {
        var before = metrics.snapshot().summary();
        ticket("URGENT", "NEW", Instant.now().plus(Duration.ofDays(2)));
        ticket("URGENT", "NEW", Instant.now().plus(Duration.ofDays(2)));
        ticket("MEDIUM", "NEW", Instant.now().minusSeconds(60));
        ticket("URGENT", "CLOSED", Instant.now().minusSeconds(60));
        repository.flush();
        var result = metrics.snapshot().summary();
        assertThat(result.slaRiskTickets()).isEqualTo(before.slaRiskTickets() + 1);
        assertThat(result.urgentTickets()).isEqualTo(before.urgentTickets() + 2);
    }
    @Test
    void createdAndRecordedResolvedCountsComeFromPersistedDates() {
        var before = metrics.snapshot().ticketTrend().getLast();
        var resolved = ticket("MEDIUM", "RESOLVED", Instant.now().minusSeconds(60));
        resolved.setResolvedAt(Instant.now()); repository.saveAndFlush(resolved);
        ticket("MEDIUM", "CLOSED", Instant.now().minusSeconds(60));
        var after = metrics.snapshot().ticketTrend().getLast();
        assertThat(after.created()).isEqualTo(before.created() + 2);
        assertThat(after.resolved()).isEqualTo(before.resolved() + 1);
        assertThat(metrics.snapshot().ticketTrend()).hasSize(7);
    }
    @Test
    void latencyUsesRecordedSamplesAndNearestRankPercentile() {
        var ticket = ticket("MEDIUM", "NEW", Instant.now().plusSeconds(86400));
        for (int sample = 1; sample <= 20; sample++) {
            var run = new com.cyagent.supportcopilot.analysis.AnalysisRun();
            run.setId("latency-" + sample); run.setTicketId(ticket.getId());
            run.setTraceId("trace-latency"); run.setStatus("SUCCEEDED"); run.setMode("mock");
            run.setResponseJson("{}"); run.setCreatedAt(Instant.now()); run.setDurationMs(sample * 100L);
            database.persist(run);
        }
        database.flush();
        assertThat(operational.snapshot().latency()).isEqualTo(new MetricsService.Latency(1050, 1900));
    }
    private Ticket ticket(String priority, String status, Instant deadline) {
        TestTrustedActors.authenticate("metrics-agent", "SUPPORT_AGENT");
        var response = tickets.create(new TicketDtos.CreateTicketRequest(TicketDomain.Channel.EMAIL,
            "合成客户", "指标测试企业", TicketDomain.CustomerTier.STANDARD, "运营指标测试", "合成内容", "zh-CN"));
        var ticket = repository.findById(response.id()).orElseThrow();
        ticket.setPriority(priority); ticket.setStatus(status); ticket.setSlaDeadline(deadline);
        return repository.saveAndFlush(ticket);
    }
}
