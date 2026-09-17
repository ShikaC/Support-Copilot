package com.cyagent.supportcopilot.ticket.activity;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.UUID;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.ObjectMapper;

import com.cyagent.supportcopilot.analysis.AnalysisPersistenceService;
import com.cyagent.supportcopilot.analysis.MockAnalysisFactory;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewService;
import com.cyagent.supportcopilot.audit.AuditEvent;
import com.cyagent.supportcopilot.audit.AuditEventRepository;
import com.cyagent.supportcopilot.common.TestTrustedActors;
import com.cyagent.supportcopilot.ticket.TicketDomain;
import com.cyagent.supportcopilot.ticket.TicketDtos;
import com.cyagent.supportcopilot.ticket.TicketNoteController.CreateNoteRequest;
import com.cyagent.supportcopilot.ticket.TicketNoteService;
import com.cyagent.supportcopilot.ticket.TicketRepository;
import com.cyagent.supportcopilot.ticket.TicketService;
import com.cyagent.supportcopilot.ticket.activity.TicketActivityController.ActivityPage;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
class TicketActivityApiTests {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;
    @Autowired TicketService tickets;
    @Autowired TicketRepository repository;
    @Autowired TicketNoteService notes;
    @Autowired AnalysisPersistenceService analysis;
    @Autowired AnalysisReviewService reviews;
    @Autowired MockAnalysisFactory mockAnalysis;
    @Autowired AuditEventRepository audit;

    @AfterEach
    void clearIdentity() { TestTrustedActors.clear(); }

    @Test
    void returnsEveryDurableBusinessActionWithoutSensitiveContentsOrUnrelatedTickets() throws Exception {
        var ticket = create();
        var updated = tickets.update(ticket.id(), new TicketDtos.UpdateTicketRequest(null,
            TicketDomain.Priority.HIGH, null, "Sensitive assignee name", ticket.version()));
        var unassigned = tickets.unassign(ticket.id(), updated.version());
        notes.add(ticket.id(), new CreateNoteRequest(UUID.randomUUID().toString(), "PRIVATE_NOTE_CANARY", unassigned.version()));
        var current = repository.findById(ticket.id()).orElseThrow();
        var first = mockAnalysis.createMock(current);
        var firstSourceVersion = current.getVersion();
        analysis.persist(ticket.id(), firstSourceVersion, first);
        TestTrustedActors.authenticate("activity-reviewer", "SUPPORT_REVIEWER");
        reviews.review(ticket.id(), first.id(), first.suggestedReply().content());
        reviews.review(ticket.id(), first.id(), "PRIVATE_REPLY_CANARY");
        reviews.reject(ticket.id(), first.id(), "PRIVATE_REJECTION_CANARY");
        current = repository.findById(ticket.id()).orElseThrow();
        var second = mockAnalysis.createMock(current);
        analysis.persist(ticket.id(), current.getVersion(), second);
        reviews.review(ticket.id(), second.id(), second.suggestedReply().content());
        var unrelated = create();
        var unrelatedTicket = repository.findById(unrelated.id()).orElseThrow();
        var unrelatedAnalysis = mockAnalysis.createMock(unrelatedTicket);
        analysis.persist(unrelated.id(), unrelatedTicket.getVersion(), unrelatedAnalysis);
        reviews.review(unrelated.id(), unrelatedAnalysis.id(), unrelatedAnalysis.suggestedReply().content());

        var response = mvc.perform(get("/api/tickets/{id}/activity", ticket.id())
            .with(jwt().authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT"))))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();

        var page = mapper.readValue(response, ActivityPage.class);
        assertThat(page.items()).hasSize(10);
        assertThat(page.items()).extracting(item -> item.action().name()).containsExactlyInAnyOrder(
            "TICKET_CREATED", "TICKET_UPDATED", "TICKET_UNASSIGNED", "TICKET_NOTE_ADDED",
            "ANALYSIS_PERSISTED", "ANALYSIS_PERSISTED", "ANALYSIS_REVIEW_APPROVED",
            "ANALYSIS_REVIEW_APPROVED", "ANALYSIS_REVIEW_EDITED", "ANALYSIS_REVIEW_REJECTED");
        assertThat(page.items()).allSatisfy(item -> {
            assertThat(item.actorLabel()).isEqualTo("已认证操作人");
            assertThat(item.traceId()).isNotBlank();
            assertThat(item.ticketVersion()).isNotNull();
        });
        assertThat(page.items().stream().filter(item -> item.action().name().equals("ANALYSIS_PERSISTED")))
            .extracting(TicketActivityController.ActivityItem::ticketVersion).contains(firstSourceVersion);
        assertThat(page.nextCursor()).isNull();
        assertThat(response).doesNotContain("PRIVATE_NOTE_CANARY", "PRIVATE_REPLY_CANARY", "PRIVATE_REJECTION_CANARY",
            "PRIVATE_CUSTOMER_CANARY", "Sensitive assignee name", "actorRoles", "metadataJson", "actorSubject", "activity-agent", "activity-reviewer", unrelated.id());
    }

    @Test
    void cursorPaginatesEqualTimestampsWithoutDuplicatesOrGaps() throws Exception {
        var ticket = create();
        var timestamp = Instant.parse("2030-01-01T00:00:00Z");
        for (var suffix : List.of("a", "b", "c", "d", "e")) {
            audit.insert(new AuditEvent("audit-tie-" + suffix, "activity-agent", "AUTHENTICATED_JWT", "[]",
                "TICKET_NOTE_ADDED", "TICKET", ticket.id(), 1L, "trace-tie-" + suffix, "{}", timestamp));
        }
        var collected = new ArrayList<String>();
        String cursor = null;
        do {
            var request = get("/api/tickets/{id}/activity", ticket.id()).param("limit", "2")
                .with(jwt().authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT")));
            if (cursor != null) request.param("cursor", cursor);
            var response = mvc.perform(request).andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
            var page = mapper.readValue(response, ActivityPage.class);
            assertThat(page.items()).hasSizeLessThanOrEqualTo(2);
            collected.addAll(page.items().stream().map(TicketActivityController.ActivityItem::id).toList());
            cursor = page.nextCursor();
        } while (cursor != null);
        assertThat(collected).hasSize(6).doesNotHaveDuplicates();
        assertThat(collected.subList(0, 5)).containsExactly("audit-tie-e", "audit-tie-d", "audit-tie-c", "audit-tie-b", "audit-tie-a");
    }

    @Test
    void rejectsInvalidPageCursorAndCrossTicketCursor() throws Exception {
        var ticket = create();
        for (var limit : List.of("0", "101", "abc")) {
            mvc.perform(get("/api/tickets/{id}/activity", ticket.id()).param("limit", limit)
                .with(jwt().authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT"))))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("code").value("INVALID_TICKET_PAGE"));
        }
        var wrongTicketCursor = Base64.getUrlEncoder().withoutPadding().encodeToString(mapper.writeValueAsBytes(
            new TicketActivityService.Cursor("different-ticket", Instant.now(), "audit-other")));
        for (var cursor : List.of("!invalid!", "x".repeat(1025), wrongTicketCursor,
            Base64.getUrlEncoder().encodeToString("{}".getBytes(java.nio.charset.StandardCharsets.UTF_8)),
            Base64.getUrlEncoder().encodeToString("null".getBytes(java.nio.charset.StandardCharsets.UTF_8)))) {
            mvc.perform(get("/api/tickets/{id}/activity", ticket.id()).param("cursor", cursor)
                .with(jwt().authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT"))))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("code").value("INVALID_TICKET_CURSOR"));
        }
    }

    @Test
    void usesTicketPermissionsAndReturnsNotFoundForMissingTicket() throws Exception {
        TestTrustedActors.clear();
        mvc.perform(get("/api/tickets/missing/activity")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/tickets/missing/activity")
            .with(jwt().authorities(new SimpleGrantedAuthority("ROLE_OTHER"))))
            .andExpect(status().isForbidden());
        for (var role : List.of("SUPPORT_AGENT", "SUPPORT_REVIEWER", "SUPPORT_ADMIN")) {
            mvc.perform(get("/api/tickets/missing/activity")
                .with(jwt().authorities(new SimpleGrantedAuthority("ROLE_" + role))))
                .andExpect(status().isNotFound());
        }
    }

    private TicketDtos.TicketResponse create() {
        TestTrustedActors.authenticate("activity-agent", "SUPPORT_AGENT");
        return tickets.create(new TicketDtos.CreateTicketRequest(TicketDomain.Channel.EMAIL, "Synthetic customer",
            "Synthetic company", TicketDomain.CustomerTier.STANDARD, "Activity test", "PRIVATE_CUSTOMER_CANARY", "zh-CN"));
    }
}
