package com.cyagent.supportcopilot.metrics;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import jakarta.persistence.EntityManager;
import jakarta.persistence.Tuple;
import org.springframework.stereotype.Repository;

@Repository
public class OperationalMetrics {
    private final EntityManager database;
    public OperationalMetrics(EntityManager database) { this.database = database; }

    public Snapshot snapshot() {
        var now = Instant.now();
        var open = "t.status not in ('RESOLVED', 'CLOSED')";
        long count = database.createQuery("select count(t) from Ticket t where " + open, Long.class).getSingleResult();
        long urgent = database.createQuery("select count(t) from Ticket t where " + open + " and t.priority = 'URGENT'", Long.class).getSingleResult();
        long risk = database.createQuery("select count(t) from Ticket t where " + open + " and t.slaDeadline <= :deadline", Long.class)
            .setParameter("deadline", now.plusSeconds(7200)).getSingleResult();
        var categories = new HashMap<String, Long>();
        database.createQuery("select t.category, count(t) from Ticket t where " + open + " group by t.category", Tuple.class)
            .getResultList().forEach(row -> categories.put(row.get(0, String.class), row.get(1, Long.class)));
        var today = LocalDate.ofInstant(now, ZoneOffset.UTC);
        var created = countsByDate("createdAt", today);
        var resolved = countsByDate("resolvedAt", today);
        var trend = new ArrayList<MetricsService.Trend>();
        for (int days = 6; days >= 0; days--) {
            var date = today.minusDays(days);
            trend.add(new MetricsService.Trend(date.toString(), Math.toIntExact(created.getOrDefault(date, 0L)), Math.toIntExact(resolved.getOrDefault(date, 0L))));
        }
        var durations = database.createQuery("select r.durationMs from AnalysisRun r where r.durationMs is not null order by r.createdAt desc, r.id desc", Long.class)
            .setMaxResults(1000).getResultList();
        MetricsService.Latency latency = null;
        if (!durations.isEmpty()) {
            var sorted = durations.stream().sorted().toList();
            long average = Math.round(sorted.stream().mapToLong(Long::longValue).average().orElseThrow());
            long p95 = sorted.get((int) Math.ceil(sorted.size() * .95) - 1);
            latency = new MetricsService.Latency(average, p95);
        }
        return new Snapshot(count, urgent, risk, categories, trend, latency);
    }

    private Map<LocalDate, Long> countsByDate(String field, LocalDate today) {
        var since = today.minusDays(6).atStartOfDay(ZoneOffset.UTC).toInstant();
        var until = today.plusDays(1).atStartOfDay(ZoneOffset.UTC).toInstant();
        var expression = "t." + field;
        var aggregates = new ArrayList<String>();
        for (int day = 0; day < 7; day++) {
            aggregates.add("sum(case when " + expression + " >= :start" + day
                + " and " + expression + " < :end" + day + " then 1 else 0 end)");
        }
        var query = database.createQuery("select " + String.join(", ", aggregates)
            + " from Ticket t where " + expression + " >= :since and " + expression + " < :until", Tuple.class)
            .setParameter("since", since).setParameter("until", until);
        for (int day = 0; day < 7; day++) {
            var start = today.minusDays(6 - day).atStartOfDay(ZoneOffset.UTC).toInstant();
            query.setParameter("start" + day, start).setParameter("end" + day, start.plusSeconds(86400));
        }
        var row = query.getSingleResult();
        var result = new HashMap<LocalDate, Long>();
        for (int day = 0; day < 7; day++) {
            var count = row.get(day, Long.class);
            result.put(today.minusDays(6 - day), count == null ? 0L : count);
        }
        return result;
    }
    public record Snapshot(long open, long urgent, long risk, Map<String, Long> categories,
        List<MetricsService.Trend> trend, MetricsService.Latency latency) {}
}
