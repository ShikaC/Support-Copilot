package com.cyagent.supportcopilot.ticket;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.http.MediaType.APPLICATION_JSON;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import com.cyagent.supportcopilot.analysis.AnalysisService;
import com.cyagent.supportcopilot.analysis.TicketVersionConflictException;
import com.cyagent.supportcopilot.common.ApiExceptionHandler;

class TicketAnalysisConflictApiTests {

	@Test
	void returnsStructuredConflictWhenAnalysisUsesAnOldTicketVersion() throws Exception {
		var ticketService = mock(TicketService.class);
		var analysisService = mock(AnalysisService.class);
		var mockMvc = mockMvc(ticketService, analysisService);
		when(analysisService.analyze("ticket-10042"))
			.thenThrow(new TicketVersionConflictException("ticket-10042", 3, 4));

		// 模拟旧版本分析到达接口，接口应把业务冲突转换为 409。
		mockMvc.perform(post("/api/tickets/ticket-10042/analyze").header("X-Trace-Id", "trace-test"))
			.andExpect(status().isConflict())
			.andExpect(jsonPath("$.code").value("VERSION_CONFLICT"))
			.andExpect(jsonPath("$.traceId").value("trace-test"))
			.andExpect(jsonPath("$.details.ticketId").value("ticket-10042"))
			.andExpect(jsonPath("$.details.expectedVersion").value(3))
			.andExpect(jsonPath("$.details.currentVersion").value(4));
	}

	@Test
	void exposesExplicitUnassignCommand() throws Exception {
		var ticketService = mock(TicketService.class);
		var analysisService = mock(AnalysisService.class);
		var mockMvc = mockMvc(ticketService, analysisService);
		var updated = new TicketDtos.TicketResponse(
			"ticket-10042", "SC-10042", "EMAIL", "测试客户", "测试公司", "STANDARD",
			"测试主题", "测试描述", "zh-CN", "BILLING", "HIGH", "IN_PROGRESS", null,
			java.time.Instant.now(), java.time.Instant.now(), java.time.Instant.now(), 4, null, java.util.List.of()
		);
		when(ticketService.unassign("ticket-10042", 3)).thenReturn(updated);

		mockMvc.perform(post("/api/tickets/ticket-10042/unassign")
				.contentType(APPLICATION_JSON)
				.content("{\"expectedVersion\":3}"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.version").value(4));

		verify(ticketService).unassign("ticket-10042", 3);
	}

	private MockMvc mockMvc(TicketService ticketService, AnalysisService analysisService) {
		return MockMvcBuilders
			.standaloneSetup(new TicketController(ticketService, analysisService))
			.setControllerAdvice(new ApiExceptionHandler())
			.build();
	}
}
