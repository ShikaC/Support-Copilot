package com.cyagent.supportcopilot.ticket;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.ObjectMapper;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("demo")
@Transactional
class TicketQueueIntegrationTests {
	@Autowired MockMvc mvc;
	@Autowired TicketRepository repository;
	@Autowired ObjectMapper mapper;
	private String keyword;
	private String oldestId;

    @Test
    void crossOriginClientsCanReadMatchingTotalAndContinuation() throws Exception {
        mvc.perform(get("/api/tickets").param("keyword", keyword).param("limit", "2")
                .header("Origin", "http://localhost:5173"))
            .andExpect(status().isOk())
            .andExpect(header().string("Access-Control-Expose-Headers", org.hamcrest.Matchers.containsString("X-Total-Count")))
            .andExpect(header().string("X-Total-Count", "35"));
    }

	@BeforeEach
	void seedMoreThanOnePageWithTiedSortKeys() {
		keyword = "queue-" + UUID.randomUUID();
		var time = Instant.parse("2026-01-01T00:00:00Z");
		for (var index = 0; index < 35; index++) {
			var ticket = new Ticket();
			ticket.setId(keyword + "-" + String.format("%02d", index));
			ticket.setTicketNo("SC-" + UUID.randomUUID().toString().substring(0, 20));
			ticket.setSubject("合成队列工单");
			ticket.setDescription(keyword + " description-only!_%");
			ticket.setCustomerName("测试客户");
			ticket.setCustomerCompany("测试企业");
			ticket.setCustomerTier("STANDARD");
			ticket.setChannel("EMAIL");
			ticket.setLanguage("zh-CN");
			ticket.setCategory("GENERAL");
			ticket.setStatus("NEW");
			ticket.setPriority(index == 0 ? "URGENT" : index % 2 == 0 ? "HIGH" : "LOW");
			ticket.setAssigneeName(index % 2 == 0 ? "队列专员" : null);
			ticket.setCreatedAt(index == 0 ? time.minusSeconds(3600) : time);
			ticket.setUpdatedAt(time);
			ticket.setSlaDeadline(index == 0 ? time.minusSeconds(3600) : time.plusSeconds((index % 3) * 60));
			repository.save(ticket);
			if (index == 0) oldestId = ticket.getId();
		}
		repository.flush();
	}

	@ParameterizedTest
	@ValueSource(strings = {"SLA", "PRIORITY"})
	void putsOldUrgentOverdueTicketBeforeTheNewestTwenty(String sort) throws Exception {
		mvc.perform(get("/api/tickets").param("keyword", keyword).param("sort", sort))
			.andExpect(status().isOk()).andExpect(header().string("X-Total-Count", "35"))
			.andExpect(jsonPath("$.length()").value(20)).andExpect(jsonPath("$[0].id").value(oldestId));
	}

	@ParameterizedTest
	@ValueSource(strings = {"NEWEST", "SLA", "PRIORITY"})
	void traversesTiedKeysWithoutRepeatingOrSkippingTickets(String sort) throws Exception {
		var ids = new ArrayList<String>();
		String cursor = null;
		do {
			var request = get("/api/tickets").param("keyword", keyword).param("sort", sort).param("limit", "7");
			if (cursor != null) request.param("cursor", cursor);
			var response = mvc.perform(request).andExpect(status().isOk())
				.andExpect(header().string("X-Total-Count", "35")).andReturn().getResponse();
			for (var item : mapper.readTree(response.getContentAsString())) ids.add(item.get("id").asText());
			cursor = response.getHeader("X-Next-Cursor");
			assertThat(ids.size()).isLessThanOrEqualTo(35);
		} while (cursor != null);
		assertThat(ids).hasSize(35).doesNotHaveDuplicates();
		assertThat(ids).contains(oldestId);
	}

	@Test
	void filtersDescriptionAndAssignmentAcrossWholeQueue() throws Exception {
		mvc.perform(get("/api/tickets").param("keyword", keyword + " description-only!_%")
			.param("assignee", "UNASSIGNED").param("limit", "100"))
			.andExpect(status().isOk()).andExpect(header().string("X-Total-Count", "17"))
			.andExpect(jsonPath("$.length()").value(17));
		mvc.perform(get("/api/tickets").param("keyword", keyword).param("assignee", "队列专员"))
			.andExpect(status().isOk()).andExpect(header().string("X-Total-Count", "18"))
			.andExpect(jsonPath("$.length()").value(18));
	}

	@Test
	void rejectsCursorUsedForDifferentSortOrFilters() throws Exception {
		var cursor = mvc.perform(get("/api/tickets").param("keyword", keyword).param("limit", "2"))
			.andExpect(status().isOk()).andReturn().getResponse().getHeader("X-Next-Cursor");
		for (var param : List.of("sort", "status", "priority", "category", "assignee", "keyword")) {
			var value = switch (param) {
				case "sort" -> "SLA";
				case "status" -> "NEW";
				case "priority" -> "HIGH";
				case "category" -> "GENERAL";
				case "assignee" -> "UNASSIGNED";
				default -> keyword + "different";
			};
			var request = get("/api/tickets").param("cursor", cursor).param(param, value);
			if (!param.equals("keyword")) request.param("keyword", keyword);
			mvc.perform(request).andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_TICKET_CURSOR"));
		}
	}

	@Test
	void rejectsUnsupportedSortAndLegacyCursorWithStableClientErrors() throws Exception {
		mvc.perform(get("/api/tickets").param("sort", "RANDOM"))
			.andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("INVALID_TICKET_FILTER"));
		mvc.perform(get("/api/tickets").param("cursor", new TicketCursor(Instant.now(), oldestId).encode()))
			.andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("INVALID_TICKET_CURSOR"));
	}
}
