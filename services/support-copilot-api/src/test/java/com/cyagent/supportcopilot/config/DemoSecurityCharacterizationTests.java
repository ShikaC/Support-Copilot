package com.cyagent.supportcopilot.config;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import com.cyagent.supportcopilot.identity.TrustedActorProvider;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("demo")
class DemoSecurityCharacterizationTests {

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private TrustedActorProvider trustedActorProvider;

	@Test
	void demoBusinessApiIsPublicWithoutCredentials() throws Exception {
		mockMvc.perform(get("/api/tickets"))
			.andExpect(status().isOk());
	}

	@Test
	void demoUsesAnExplicitAnonymousDemoActor() {
		var actor = trustedActorProvider.currentActor();

		org.assertj.core.api.Assertions.assertThat(actor.type().name()).isEqualTo("UNAUTHENTICATED_DEMO");
		org.assertj.core.api.Assertions.assertThat(actor.subject()).isEqualTo("anonymous-demo");
		org.assertj.core.api.Assertions.assertThat(actor.displayLabel()).isEqualTo("匿名演示操作人");
	}
}
