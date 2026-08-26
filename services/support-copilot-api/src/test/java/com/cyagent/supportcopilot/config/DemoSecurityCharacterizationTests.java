package com.cyagent.supportcopilot.config;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import com.cyagent.supportcopilot.analysis.review.ReviewActorProvider;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("demo")
class DemoSecurityCharacterizationTests {

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private ReviewActorProvider reviewActorProvider;

	@Test
	void demoBusinessApiIsPublicWithoutCredentials() throws Exception {
		mockMvc.perform(get("/api/tickets"))
			.andExpect(status().isOk());
	}

	@Test
	void demoUsesAnExplicitAnonymousDemoActor() {
		var actor = reviewActorProvider.currentActor();

		org.assertj.core.api.Assertions.assertThat(actor.type()).isEqualTo("UNAUTHENTICATED_DEMO");
		org.assertj.core.api.Assertions.assertThat(actor.label()).isEqualTo("匿名演示操作人");
	}
}
