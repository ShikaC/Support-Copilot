package com.cyagent.supportcopilot.config;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.core.env.Environment;
import org.springframework.test.context.ActiveProfiles;

import com.cyagent.supportcopilot.analysis.AnalysisRunRepository;
import com.cyagent.supportcopilot.ticket.TicketRepository;

@SpringBootTest
@ActiveProfiles("demo")
class DemoProfileIntegrationTests {

	@Autowired
	private TicketRepository ticketRepository;

	@Autowired
	private AnalysisRunRepository analysisRunRepository;

	@Autowired
	private Environment environment;

	@Test
	void startsWithDemoFixturesAndH2ConsoleEnabled() {
		assertThat(ticketRepository.count()).isEqualTo(8);
		assertThat(analysisRunRepository.count()).isEqualTo(7);
		assertThat(environment.getProperty("spring.h2.console.enabled")).isEqualTo("true");
	}
}
