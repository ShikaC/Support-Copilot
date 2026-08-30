package com.cyagent.supportcopilot.ticket;

import static org.hamcrest.Matchers.isEmptyOrNullString;
import static org.hamcrest.Matchers.not;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("demo")
class TicketPaginationIntegrationTests {

	@Autowired
	private MockMvc mockMvc;

	@Test
	void returnsStableKeysetPagesAndContinuationHeader() throws Exception {
		var firstPage = mockMvc.perform(get("/api/tickets").param("limit", "2"))
			.andExpect(status().isOk())
			.andExpect(header().string("X-Page-Limit", "2"))
			.andExpect(header().string("X-Next-Cursor", not(isEmptyOrNullString())))
			.andExpect(jsonPath("$.length()").value(2))
			.andExpect(jsonPath("$[0].id").value("ticket-10042"))
			.andExpect(jsonPath("$[1].id").value("ticket-10041"))
			.andReturn();

		var cursor = firstPage.getResponse().getHeader("X-Next-Cursor");
		mockMvc.perform(get("/api/tickets").param("limit", "2").param("cursor", cursor))
			.andExpect(status().isOk())
			.andExpect(header().string("X-Page-Limit", "2"))
			.andExpect(jsonPath("$.length()").value(2))
			.andExpect(jsonPath("$[0].id").value("ticket-10039"))
			.andExpect(jsonPath("$[1].id").value("ticket-10037"));
	}

	@Test
	void appliesCategoryAndKeywordFiltersBeforePaging() throws Exception {
		mockMvc.perform(get("/api/tickets")
				.param("category", "ACCOUNT_ACCESS")
				.param("keyword", "SSO")
				.param("limit", "1"))
			.andExpect(status().isOk())
			.andExpect(header().string("X-Page-Limit", "1"))
			.andExpect(jsonPath("$.length()").value(1))
			.andExpect(jsonPath("$[0].ticketNo").value("SC-10041"));
	}

	@Test
	void treatsLikeMetacharactersAsLiteralKeywordText() throws Exception {
		mockMvc.perform(get("/api/tickets")
				.param("keyword", "%")
				.param("limit", "100"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.length()").value(0));
	}

	@Test
	void returnsStableErrorsForInvalidPaginationParameters() throws Exception {
		mockMvc.perform(get("/api/tickets").param("limit", "0"))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.code").value("INVALID_TICKET_PAGE"));

		mockMvc.perform(get("/api/tickets").param("cursor", "not-a-cursor"))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.code").value("INVALID_TICKET_CURSOR"));

		mockMvc.perform(get("/api/tickets").param("limit", "abc"))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.code").value("INVALID_TICKET_PAGE"));
	}
}
