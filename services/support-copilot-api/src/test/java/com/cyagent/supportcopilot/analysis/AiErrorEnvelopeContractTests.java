package com.cyagent.supportcopilot.analysis;

import static org.mockito.Mockito.mock;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import com.cyagent.supportcopilot.common.ApiExceptionHandler;
import com.cyagent.supportcopilot.common.TraceIdFilter;
import com.cyagent.supportcopilot.ticket.TicketRepository;

class AiErrorEnvelopeContractTests {

	@ParameterizedTest
	@CsvSource({
		"/auth,AI_SERVICE_AUTHENTICATION_FAILED",
		"/request,AI_SERVICE_REQUEST_REJECTED",
		"/contract,AI_SERVICE_CONTRACT_ERROR"
	})
	void nonFallbackAiFailuresReturnStableTraceableRedactedEnvelope(
		String path,
		String code
	) throws Exception {
		var mockMvc = MockMvcBuilders.standaloneSetup(new FaultController())
			.setControllerAdvice(new ApiExceptionHandler(mock(TicketRepository.class)))
			.addFilters(new TraceIdFilter())
			.build();

		mockMvc.perform(get(path)
				.header("X-Trace-Id", "trace-ai-envelope")
				.header("Authorization", "Bearer secret-auth-value"))
			.andExpect(status().isBadGateway())
			.andExpect(header().string("X-Trace-Id", "trace-ai-envelope"))
			.andExpect(jsonPath("$.code").value(code))
			.andExpect(jsonPath("$.traceId").value("trace-ai-envelope"))
			.andExpect(jsonPath("$.details").isMap())
			.andExpect(content().string(org.hamcrest.Matchers.not(
				org.hamcrest.Matchers.containsString("secret-auth-value")
			)));
	}

	@RestController
	private static final class FaultController {

		@GetMapping("/auth")
		void auth() {
			throw new AiServiceAuthenticationException(new IllegalStateException("hidden"));
		}

		@GetMapping("/request")
		void request() {
			throw new AiServiceRequestException(422, new IllegalStateException("hidden"));
		}

		@GetMapping("/contract")
		void contract() {
			throw new AiServiceContractException("hidden");
		}
	}
}
