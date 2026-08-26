package com.cyagent.supportcopilot.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.sql.SQLException;

import javax.sql.DataSource;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.core.env.Environment;
import org.springframework.test.context.ActiveProfiles;

import com.cyagent.supportcopilot.analysis.AnalysisRunRepository;
import com.cyagent.supportcopilot.ticket.TicketRepository;

@SpringBootTest
@ActiveProfiles("test")
class TestProfileIntegrationTests {

	@Autowired
	private TicketRepository ticketRepository;

	@Autowired
	private AnalysisRunRepository analysisRunRepository;

	@Autowired
	private DataSource dataSource;

	@Autowired
	private Environment environment;

	@Test
	void startsWithAnIsolatedEmptyH2Database() throws SQLException {
		try (var connection = dataSource.getConnection()) {
			assertThat(connection.getMetaData().getURL())
				.startsWith("jdbc:h2:mem:supportcopilot-test-");
		}
		assertThat(ticketRepository.count()).isZero();
		assertThat(analysisRunRepository.count()).isZero();
		assertThat(environment.getProperty("spring.h2.console.enabled")).isEqualTo("false");
	}
}
