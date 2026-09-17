package com.cyagent.supportcopilot.ticket;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import com.cyagent.supportcopilot.common.TestTrustedActors;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class TicketWorkspaceCommandTests {
    @Autowired MockMvc mvc;
    @Autowired TicketService tickets;
    @Autowired TicketNoteService notes;
    @Autowired TicketRepository repository;
    @Autowired JdbcTemplate jdbc;
    @AfterEach void clearActor() { TestTrustedActors.clear(); }

    private TicketDtos.TicketResponse create() {
        TestTrustedActors.authenticate("command-agent", "SUPPORT_AGENT");
        return tickets.create(new TicketDtos.CreateTicketRequest(TicketDomain.Channel.EMAIL,
            "合成客户", "合成企业", TicketDomain.CustomerTier.STANDARD, "并发命令验收", "合成描述", "zh-CN"));
    }
    @Test
    void creationReplayReturnsSameTicketAndChangedPayloadConflicts() throws Exception {
        var key = UUID.randomUUID().toString();
        var body = "{\"channel\":\"EMAIL\",\"customerName\":\"合成客户\",\"customerCompany\":\"合成企业\",\"customerTier\":\"STANDARD\",\"subject\":\"创建重试\",\"description\":\"合成描述\",\"language\":\"zh-CN\"}";
        var before = repository.count();
        var first = mvc.perform(post("/api/tickets/commands/create").with(jwt().authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT")))
            .header("Idempotency-Key", key).contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isCreated()).andReturn().getResponse().getContentAsString();
        var replay = mvc.perform(post("/api/tickets/commands/create").with(jwt().authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT")))
            .header("Idempotency-Key", key).contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isCreated()).andReturn().getResponse().getContentAsString();
        assertThat(replay).isEqualTo(first);
        assertThat(repository.count()).isEqualTo(before + 1);
        mvc.perform(post("/api/tickets/commands/create").with(jwt().authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT")))
            .header("Idempotency-Key", key).contentType(MediaType.APPLICATION_JSON).content(body.replace("创建重试", "不同内容")))
            .andExpect(status().isConflict());
        assertThat(repository.count()).isEqualTo(before + 1);
    }
    @Test
    void simultaneousSameTicketReplayWritesOneNoteAndOneAuditEvent() throws Exception {
        var ticket = create();
        var request = new TicketNoteController.CreateNoteRequest(UUID.randomUUID().toString(), "并发备注", ticket.version());
        var start = new CountDownLatch(1);
        try (var executor = Executors.newFixedThreadPool(2)) {
            var first = executor.submit(() -> addAfter(start, ticket.id(), request));
            var second = executor.submit(() -> addAfter(start, ticket.id(), request));
            start.countDown();
            var a = first.get(10, TimeUnit.SECONDS);
            var b = second.get(10, TimeUnit.SECONDS);
            assertThat(a.id()).isEqualTo(b.id());
            assertThat(notes.list(ticket.id())).hasSize(1);
            assertThat(repository.findById(ticket.id()).orElseThrow().getVersion()).isEqualTo(ticket.version() + 1);
            assertThat(jdbc.queryForObject("select count(*) from audit_events where action = 'TICKET_NOTE_ADDED' and target_id = ?", Integer.class, ticket.id())).isEqualTo(1);
        }
    }
    @Test
    void sameRequestIdOnDifferentTicketsIsIndependentlyScoped() throws Exception {
        var a = create(); var b = create();
        var key = UUID.randomUUID().toString(); var start = new CountDownLatch(1);
        try (var executor = Executors.newFixedThreadPool(2)) {
            var first = executor.submit(() -> addAfter(start, a.id(), new TicketNoteController.CreateNoteRequest(key, "并发备注", a.version())));
            var second = executor.submit(() -> addAfter(start, b.id(), new TicketNoteController.CreateNoteRequest(key, "并发备注", b.version())));
            start.countDown();
            assertThat(first.get(10, TimeUnit.SECONDS).id()).isNotEqualTo(second.get(10, TimeUnit.SECONDS).id());
            assertThat(notes.list(a.id())).hasSize(1); assertThat(notes.list(b.id())).hasSize(1);
        }
    }
    @Test
    void claimUsesTrustedIdentityAndRejectsAStaleVersion() throws Exception {
        var ticket = create();
        mvc.perform(post("/api/tickets/{id}/claim", ticket.id()).with(jwt().jwt(j -> j.subject("real-agent").claim("name", "真实客服"))
            .authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT")))
            .header("X-Actor-Subject", "spoofed").contentType(MediaType.APPLICATION_JSON)
            .content("{\"expectedVersion\":" + ticket.version() + "}"))
            .andExpect(status().isOk());
        assertThat(repository.findById(ticket.id()).orElseThrow().getAssigneeName()).isEqualTo("real-agent");
        mvc.perform(post("/api/tickets/{id}/claim", ticket.id()).with(jwt().authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT")))
            .contentType(MediaType.APPLICATION_JSON).content("{\"expectedVersion\":" + ticket.version() + "}"))
            .andExpect(status().isConflict());
    }
    private TicketNoteController.NoteResponse addAfter(CountDownLatch start, String id, TicketNoteController.CreateNoteRequest request) throws Exception {
        start.await(5, TimeUnit.SECONDS);
        TestTrustedActors.authenticate("command-agent", "SUPPORT_AGENT");
        try { return notes.add(id, request); } finally { TestTrustedActors.clear(); }
    }
}
