package com.cyagent.supportcopilot.idempotency;

import static org.assertj.core.api.Assertions.assertThat;

import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.jdbc.core.JdbcTemplate;

import com.cyagent.supportcopilot.analysis.AnalysisRunRepository;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewRepository;

final class CommandIdempotencyAssertions {

	private CommandIdempotencyAssertions() {
	}

	static void assertCounts(
		ConfigurableApplicationContext context,
		long analyses,
		long reviews,
		long audits,
		long commands
	) {
		assertThat(context.getBean(AnalysisRunRepository.class).count()).isEqualTo(analyses);
		assertThat(context.getBean(AnalysisReviewRepository.class).count()).isEqualTo(reviews);
		var jdbc = context.getBean(JdbcTemplate.class);
		assertThat(jdbc.queryForObject("select count(*) from audit_events", Long.class)).isEqualTo(audits);
		assertThat(jdbc.queryForObject("select count(*) from command_idempotency", Long.class))
			.isEqualTo(commands);
	}
}
