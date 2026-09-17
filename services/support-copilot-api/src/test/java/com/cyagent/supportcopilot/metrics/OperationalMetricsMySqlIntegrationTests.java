package com.cyagent.supportcopilot.metrics;

import static com.cyagent.supportcopilot.common.MySqlTestSupport.container;
import static com.cyagent.supportcopilot.common.MySqlTestSupport.startContext;
import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import com.cyagent.supportcopilot.ticket.TicketRepository;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.mysql.MySQLContainer;
import com.cyagent.supportcopilot.analysis.AnalysisRun;
import com.cyagent.supportcopilot.analysis.AnalysisRunRepository;
import com.cyagent.supportcopilot.common.TestTrustedActors;

@EnabledIfEnvironmentVariable(named = "SUPPORT_COPILOT_RUN_MYSQL_TESTS", matches = "true")
@Testcontainers
class OperationalMetricsMySqlIntegrationTests {
    @Container static final MySQLContainer MYSQL = container("operational_metrics");
    @Test
    void actualDeadlineCalendarAndLatencyFactsSurviveMysqlRestart() {
        var date = LocalDate.now(ZoneOffset.UTC).toString();
        try (var context = startContext(MYSQL)) {
            TestTrustedActors.authenticate("metrics-mysql", "SUPPORT_AGENT");
            var repository = context.getBean(TicketRepository.class);
            for (int index = 0; index < 3; index++) {
                var entity = new com.cyagent.supportcopilot.ticket.Ticket();
                entity.setId("metrics-mysql-" + index); entity.setTicketNo("SC-METRICS-" + index);
                entity.setChannel("EMAIL"); entity.setCustomerName("合成客户"); entity.setCustomerCompany("合成企业");
                entity.setCustomerTier("STANDARD"); entity.setSubject("指标验证"); entity.setDescription("合成描述");
                entity.setLanguage("zh-CN"); entity.setCategory("GENERAL"); entity.setUpdatedAt(Instant.now());
                entity.setStatus(index == 2 ? "RESOLVED" : "NEW");
                entity.setPriority(index == 1 ? "URGENT" : "MEDIUM");
                entity.setSlaDeadline(Instant.now().plusSeconds(index == 1 ? 86400 : -60));
                var midnight = LocalDate.now(ZoneOffset.UTC).atStartOfDay(ZoneOffset.UTC).toInstant();
                entity.setCreatedAt(midnight.plusSeconds(index == 0 ? -1 : 1));
                if (index == 2) entity.setResolvedAt(midnight.plusSeconds(1));
                repository.saveAndFlush(entity);
                var run = new AnalysisRun();
                run.setId("mysql-latency-" + index); run.setTicketId(entity.getId());
                run.setTraceId("trace-mysql-metrics"); run.setStatus("SUCCEEDED"); run.setMode("mock");
                run.setResponseJson("{}"); run.setCreatedAt(Instant.now()); run.setDurationMs((index + 1) * 100L);
                context.getBean(AnalysisRunRepository.class).saveAndFlush(run);
            }
        } finally { org.springframework.security.core.context.SecurityContextHolder.clearContext(); }
        try (var context = startContext(MYSQL)) {
            var snapshot = context.getBean(OperationalMetrics.class).snapshot();
            assertThat(snapshot.open()).isEqualTo(2);
            assertThat(snapshot.urgent()).isEqualTo(1);
            assertThat(snapshot.risk()).isEqualTo(1);
            assertThat(snapshot.trend()).contains(new MetricsService.Trend(date, 2, 1), new MetricsService.Trend(LocalDate.parse(date).minusDays(1).toString(), 1, 0));
            assertThat(snapshot.latency()).isEqualTo(new MetricsService.Latency(200, 300));
        }
    }
}
