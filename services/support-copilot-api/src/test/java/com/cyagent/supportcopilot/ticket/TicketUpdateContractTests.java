package com.cyagent.supportcopilot.ticket;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.http.MediaType.APPLICATION_JSON;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.validation.Validator;
import org.springframework.http.converter.json.JacksonJsonHttpMessageConverter;
import org.springframework.orm.ObjectOptimisticLockingFailureException;

import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.json.JsonMapper;

import com.cyagent.supportcopilot.analysis.AnalysisService;
import com.cyagent.supportcopilot.analysis.AnalysisCommandService;
import com.cyagent.supportcopilot.analysis.TicketVersionConflictException;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewService;
import com.cyagent.supportcopilot.audit.AuditEventRecorder;
import com.cyagent.supportcopilot.common.ApiExceptionHandler;
import com.cyagent.supportcopilot.common.TestTrustedActors;
import com.cyagent.supportcopilot.ticket.TicketDomain.Priority;

@SpringBootTest
@ActiveProfiles("test")
class TicketUpdateContractTests {

	@Autowired
	private TicketRepository ticketRepository;

	@Autowired
	private TicketService ticketService;

	@Autowired
	private AnalysisService analysisService;

	@Autowired
	private AnalysisCommandService analysisCommandService;

	@Autowired
	private Validator validator;

	private MockMvc mockMvc;
	private String ticketId;

	@BeforeEach
	void setUp() {
		TestTrustedActors.authenticate("ticket-contract-test-agent", "SUPPORT_AGENT");
		mockMvc = MockMvcBuilders
			.standaloneSetup(new TicketController(ticketService, analysisService, analysisCommandService))
			.setControllerAdvice(new ApiExceptionHandler(ticketRepository))
			.setValidator(validator)
			.setMessageConverters(strictJsonConverter())
			.build();
	}

	@AfterEach
	void cleanUp() {
		TestTrustedActors.clear();
		if (ticketId != null) {
			ticketRepository.deleteById(ticketId);
		}
	}

	@Test
	void rejectsPatchWhenExpectedVersionIsMissingWithoutMutatingTicket() throws Exception {
		var ticket = saveTicket("NEW", "MEDIUM", "GENERAL", null);

		mockMvc.perform(patch("/api/tickets/{id}", ticket.getId())
				.contentType(APPLICATION_JSON)
				.content("{\"priority\":\"HIGH\"}"))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.code").value("INVALID_REQUEST"));

		var persisted = ticketRepository.findById(ticket.getId()).orElseThrow();
		assertThat(persisted.getPriority()).isEqualTo("MEDIUM");
		assertThat(persisted.getVersion()).isEqualTo(ticket.getVersion());
	}

	@Test
	void rejectsUnknownPatchFieldWithoutMutatingTicket() throws Exception {
		var ticket = saveTicket("NEW", "MEDIUM", "GENERAL", null);

		mockMvc.perform(patch("/api/tickets/{id}", ticket.getId())
				.contentType(APPLICATION_JSON)
				.content("{\"unexpected\":\"value\",\"expectedVersion\":" + ticket.getVersion() + "}"))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.code").value("INVALID_REQUEST"));

		assertThat(ticketRepository.findById(ticket.getId()).orElseThrow().getVersion())
			.isEqualTo(ticket.getVersion());
	}

	@Test
	void rejectsOverlongAssigneeWithoutMutatingTicket() throws Exception {
		var ticket = saveTicket("NEW", "MEDIUM", "GENERAL", "原负责人");
		var overlongAssignee = "负".repeat(81);

		mockMvc.perform(patch("/api/tickets/{id}", ticket.getId())
				.contentType(APPLICATION_JSON)
				.content("{\"assigneeName\":\"" + overlongAssignee + "\",\"expectedVersion\":"
					+ ticket.getVersion() + "}"))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.code").value("INVALID_REQUEST"));

		var persisted = ticketRepository.findById(ticket.getId()).orElseThrow();
		assertThat(persisted.getAssigneeName()).isEqualTo("原负责人");
		assertThat(persisted.getVersion()).isEqualTo(ticket.getVersion());
	}

	@Test
	void treatsNullOptionalFieldsAsNoOp() throws Exception {
		var ticket = saveTicket("NEW", "MEDIUM", "GENERAL", "原负责人");

		mockMvc.perform(patch("/api/tickets/{id}", ticket.getId())
				.contentType(APPLICATION_JSON)
				.content("""
					{"status":null,"priority":null,"category":null,"assigneeName":null,"expectedVersion":%d}
					""".formatted(ticket.getVersion())))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.version").value(ticket.getVersion()));

		assertThat(ticketRepository.findById(ticket.getId()).orElseThrow().getVersion())
			.isEqualTo(ticket.getVersion());
	}

	@Test
	void updatesWithCurrentVersionAndReturnsIncrementedVersion() throws Exception {
		var ticket = saveTicket("NEW", "MEDIUM", "GENERAL", null);

		mockMvc.perform(patch("/api/tickets/{id}", ticket.getId())
				.contentType(APPLICATION_JSON)
				.content("{\"priority\":\"HIGH\",\"expectedVersion\":" + ticket.getVersion() + "}"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.priority").value("HIGH"))
			.andExpect(jsonPath("$.version").value(ticket.getVersion() + 1));

		var persisted = ticketRepository.findById(ticket.getId()).orElseThrow();
		assertThat(persisted.getPriority()).isEqualTo("HIGH");
		assertThat(persisted.getVersion()).isEqualTo(ticket.getVersion() + 1);
	}

	@Test
	void rejectsStaleVersionWithDetailsAndNoFieldMutation() throws Exception {
		var ticket = saveTicket("NEW", "MEDIUM", "GENERAL", "原负责人");
		var currentVersion = ticket.getVersion();

		mockMvc.perform(patch("/api/tickets/{id}", ticket.getId())
				.header("X-Trace-Id", "trace-stale-patch")
				.contentType(APPLICATION_JSON)
				.content("{\"priority\":\"URGENT\",\"assigneeName\":\"新负责人\",\"expectedVersion\":"
					+ (currentVersion + 1) + "}"))
			.andExpect(status().isConflict())
			.andExpect(jsonPath("$.code").value("VERSION_CONFLICT"))
			.andExpect(jsonPath("$.traceId").value("trace-stale-patch"))
			.andExpect(jsonPath("$.details.expectedVersion").value(currentVersion + 1))
			.andExpect(jsonPath("$.details.currentVersion").value(currentVersion));

		var persisted = ticketRepository.findById(ticket.getId()).orElseThrow();
		assertThat(persisted.getPriority()).isEqualTo("MEDIUM");
		assertThat(persisted.getAssigneeName()).isEqualTo("原负责人");
		assertThat(persisted.getVersion()).isEqualTo(currentVersion);
	}

	@Test
	void concurrentPatchesProduceOneConflictAndNoLostUpdate() throws Exception {
		var ticket = saveTicket("NEW", "MEDIUM", "GENERAL", null);
		var sourceVersion = ticket.getVersion();
		var start = new CountDownLatch(1);
		try (var executor = Executors.newFixedThreadPool(2)) {
			var high = executor.submit(() -> updateAfter(start, ticket.getId(), sourceVersion, Priority.HIGH));
			var urgent = executor.submit(() -> updateAfter(start, ticket.getId(), sourceVersion, Priority.URGENT));
			start.countDown();

			var outcomes = List.of(high.get(), urgent.get());
			assertThat(outcomes.stream().filter(TicketDtos.TicketResponse.class::isInstance)).hasSize(1);
			assertThat(outcomes.stream().filter(TicketVersionConflictException.class::isInstance)).hasSize(1);
		}

		var persisted = ticketRepository.findById(ticket.getId()).orElseThrow();
		assertThat(persisted.getVersion()).isEqualTo(sourceVersion + 1);
		assertThat(persisted.getPriority()).isIn("HIGH", "URGENT");
	}

	@Test
	void translatesJpaOptimisticLockFailureToVersionConflictContract() {
		var repository = mock(TicketRepository.class);
		var ticket = new Ticket();
		ticket.setId("ticket-concurrent-jpa");
		ticket.setVersion(7);
		ticket.setStatus("NEW");
		when(repository.findById(ticket.getId())).thenReturn(Optional.of(ticket));
		when(repository.saveAndFlush(ticket))
			.thenThrow(new ObjectOptimisticLockingFailureException(Ticket.class, ticket.getId()));
		var service = new TicketService(
			repository,
			mock(AnalysisService.class),
			mock(AnalysisReviewService.class),
			mock(AuditEventRecorder.class)
		);

		assertThatThrownBy(() -> service.update(
			ticket.getId(),
			new TicketDtos.UpdateTicketRequest(null, Priority.HIGH, null, null, 7L)
		))
			.isInstanceOf(TicketVersionConflictException.class)
			.satisfies(exception -> {
				var conflict = (TicketVersionConflictException) exception;
				assertThat(conflict.getExpectedVersion()).isEqualTo(7L);
				assertThat(conflict.getCurrentVersion()).isNull();
			});
	}

	@Test
	void exposesCurrentVersionForJpaOptimisticLockConflict() throws Exception {
		var repository = mock(TicketRepository.class);
		var service = mock(TicketService.class);
		var current = new Ticket();
		current.setId("ticket-concurrent-jpa");
		current.setVersion(8);
		when(repository.findById(current.getId())).thenReturn(Optional.of(current));
		when(service.update(org.mockito.ArgumentMatchers.eq(current.getId()), org.mockito.ArgumentMatchers.any()))
			.thenThrow(new TicketVersionConflictException(
				current.getId(),
				7,
				null,
				new ObjectOptimisticLockingFailureException(Ticket.class, current.getId())
			));
		var mvc = MockMvcBuilders
			.standaloneSetup(new TicketController(
				service,
				mock(AnalysisService.class),
				mock(AnalysisCommandService.class)
			))
			.setControllerAdvice(new ApiExceptionHandler(repository))
			.setValidator(validator)
			.setMessageConverters(strictJsonConverter())
			.build();

		mvc.perform(patch("/api/tickets/{id}", current.getId())
				.contentType(APPLICATION_JSON)
				.content("{\"priority\":\"HIGH\",\"expectedVersion\":7}"))
			.andExpect(status().isConflict())
			.andExpect(jsonPath("$.code").value("VERSION_CONFLICT"))
			.andExpect(jsonPath("$.details.expectedVersion").value(7))
			.andExpect(jsonPath("$.details.currentVersion").value(8));
	}

	@ParameterizedTest
	@CsvSource({
		"NEW, IN_PROGRESS",
		"READY_FOR_REVIEW, IN_PROGRESS",
		"READY_FOR_MANUAL_REVIEW, IN_PROGRESS",
		"NEEDS_ESCALATION, IN_PROGRESS",
		"IN_PROGRESS, WAITING_CUSTOMER",
		"IN_PROGRESS, RESOLVED",
		"WAITING_CUSTOMER, IN_PROGRESS",
		"RESOLVED, CLOSED"
	})
	void allowsEveryManualTransition(String from, String to) throws Exception {
		var ticket = saveTicket(from, "MEDIUM", "GENERAL", "负责人");

		mockMvc.perform(patch("/api/tickets/{id}", ticket.getId())
				.contentType(APPLICATION_JSON)
				.content("{\"status\":\"" + to + "\",\"expectedVersion\":" + ticket.getVersion() + "}"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.status").value(to))
			.andExpect(jsonPath("$.version").value(ticket.getVersion() + 1));
	}

	@Test
	void preservesAssignmentOnlyPatchWithCurrentVersion() throws Exception {
		var ticket = saveTicket("READY_FOR_REVIEW", "HIGH", "BILLING", null);

		mockMvc.perform(patch("/api/tickets/{id}", ticket.getId())
				.contentType(APPLICATION_JSON)
				.content("{\"assigneeName\":\"演示管理员\",\"expectedVersion\":" + ticket.getVersion() + "}"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.assigneeName").value("演示管理员"))
			.andExpect(jsonPath("$.status").value("READY_FOR_REVIEW"));
	}

	@ParameterizedTest
	@CsvSource({
		"NEW, RESOLVED",
		"IN_PROGRESS, CLOSED",
		"WAITING_CUSTOMER, RESOLVED",
		"RESOLVED, IN_PROGRESS",
		"CLOSED, IN_PROGRESS"
	})
	void rejectsIllegalOrTerminalTransitionWithoutMutation(String from, String to) throws Exception {
		var ticket = saveTicket(from, "MEDIUM", "GENERAL", "原负责人");

		mockMvc.perform(patch("/api/tickets/{id}", ticket.getId())
				.contentType(APPLICATION_JSON)
				.content("{\"status\":\"" + to + "\",\"assigneeName\":\"新负责人\",\"expectedVersion\":"
					+ ticket.getVersion() + "}"))
			.andExpect(status().isConflict())
			.andExpect(jsonPath("$.code").value("TICKET_STATE_CONFLICT"));

		var persisted = ticketRepository.findById(ticket.getId()).orElseThrow();
		assertThat(persisted.getStatus()).isEqualTo(from);
		assertThat(persisted.getAssigneeName()).isEqualTo("原负责人");
		assertThat(persisted.getVersion()).isEqualTo(ticket.getVersion());
	}

	@ParameterizedTest
	@ValueSource(strings = {"ANALYZING", "UNKNOWN_STATUS"})
	void rejectsNonManualStatusAtHttpBoundary(String invalidStatus) throws Exception {
		assertInvalidPatch("status", invalidStatus);
	}

	@ParameterizedTest
	@ValueSource(strings = {"CRITICAL", ""})
	void rejectsInvalidPriorityAtHttpBoundary(String invalidPriority) throws Exception {
		assertInvalidPatch("priority", invalidPriority);
	}

	@ParameterizedTest
	@ValueSource(strings = {"MADE_UP", ""})
	void rejectsInvalidCategoryAtHttpBoundary(String invalidCategory) throws Exception {
		assertInvalidPatch("category", invalidCategory);
	}

	@ParameterizedTest
	@ValueSource(strings = {"SECURITY", "LEGAL"})
	void acceptsEveryHighRiskCategoryConsumedByAiPolicy(String category) throws Exception {
		var ticket = saveTicket("NEW", "MEDIUM", "GENERAL", null);
		mockMvc.perform(patch("/api/tickets/{id}", ticket.getId())
				.contentType(APPLICATION_JSON)
				.content("{\"category\":\"" + category + "\",\"expectedVersion\":" + ticket.getVersion() + "}"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.category").value(category));
	}

	@ParameterizedTest
	@ValueSource(strings = {"SMS", "UNKNOWN"})
	void rejectsInvalidCreateChannel(String invalidChannel) throws Exception {
		assertInvalidCreate(invalidChannel, "STANDARD");
	}

	@ParameterizedTest
	@ValueSource(strings = {"VIP", "UNKNOWN"})
	void rejectsInvalidCreateCustomerTier(String invalidTier) throws Exception {
		assertInvalidCreate("EMAIL", invalidTier);
	}

	private void assertInvalidPatch(String field, String value) throws Exception {
		var ticket = saveTicket("NEW", "MEDIUM", "GENERAL", null);
		mockMvc.perform(patch("/api/tickets/{id}", ticket.getId())
				.contentType(APPLICATION_JSON)
				.content("{\"" + field + "\":\"" + value + "\",\"expectedVersion\":" + ticket.getVersion() + "}"))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.code").value("INVALID_REQUEST"));

		assertThat(ticketRepository.findById(ticket.getId()).orElseThrow().getVersion())
			.isEqualTo(ticket.getVersion());
	}

	private void assertInvalidCreate(String channel, String tier) throws Exception {
		var countBefore = ticketRepository.count();
		mockMvc.perform(post("/api/tickets")
				.contentType(APPLICATION_JSON)
				.content("""
					{"channel":"%s","customerName":"客户","customerCompany":"公司","customerTier":"%s",
					 "subject":"主题","description":"描述","language":"zh-CN"}
					""".formatted(channel, tier)))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.code").value("INVALID_REQUEST"));
		assertThat(ticketRepository.count()).isEqualTo(countBefore);
	}

	private Object updateAfter(CountDownLatch start, String id, long expectedVersion, Priority priority) {
		try {
			start.await();
			TestTrustedActors.authenticate("ticket-concurrency-test-agent", "SUPPORT_AGENT");
			return ticketService.update(
				id,
				new TicketDtos.UpdateTicketRequest(null, priority, null, null, expectedVersion)
			);
		} catch (TicketVersionConflictException exception) {
			return exception;
		} catch (InterruptedException exception) {
			Thread.currentThread().interrupt();
			throw new IllegalStateException("Concurrent contract test was interrupted", exception);
		} finally {
			TestTrustedActors.clear();
		}
	}

	private JacksonJsonHttpMessageConverter strictJsonConverter() {
		return new JacksonJsonHttpMessageConverter(
			JsonMapper.builder()
				.enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
				.build()
		);
	}

	private Ticket saveTicket(String status, String priority, String category, String assigneeName) {
		var now = Instant.now();
		var ticket = new Ticket();
		ticketId = "ticket-contract-" + UUID.randomUUID();
		ticket.setId(ticketId);
		ticket.setTicketNo("SC-CONTRACT-" + UUID.randomUUID().toString().substring(0, 8));
		ticket.setChannel("EMAIL");
		ticket.setCustomerName("契约测试客户");
		ticket.setCustomerCompany("契约测试公司");
		ticket.setCustomerTier("STANDARD");
		ticket.setSubject("工单更新契约测试");
		ticket.setDescription("验证版本前置条件和字段更新不会发生漂移。");
		ticket.setLanguage("zh-CN");
		ticket.setCategory(category);
		ticket.setPriority(priority);
		ticket.setStatus(status);
		ticket.setAssigneeName(assigneeName);
		ticket.setSlaDeadline(now.plus(Duration.ofHours(8)));
		ticket.setCreatedAt(now);
		ticket.setUpdatedAt(now);
		return ticketRepository.saveAndFlush(ticket);
	}
}
