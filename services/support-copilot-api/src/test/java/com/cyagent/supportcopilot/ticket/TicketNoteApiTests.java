package com.cyagent.supportcopilot.ticket;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;
import com.cyagent.supportcopilot.common.TestTrustedActors;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
class TicketNoteApiTests {
    @Autowired MockMvc mvc;
    @Autowired TicketService tickets;
    @Autowired TicketRepository repository;
    @Autowired TicketNoteRepository notes;

    private TicketDtos.TicketResponse create() {
        TestTrustedActors.authenticate("note-agent", "SUPPORT_AGENT");
        return tickets.create(new TicketDtos.CreateTicketRequest(TicketDomain.Channel.EMAIL,
            "合成客户", "合成企业", TicketDomain.CustomerTier.STANDARD, "备注测试", "合成描述", "zh-CN"));
    }
    private String body(String noteId, long version) {
        return "{\"noteId\":\"" + noteId + "\",\"content\":\"已核对合成订单，请财务复核。\",\"expectedVersion\":" + version + "}";
    }
    @Test
    void persistsTrustedNoteAndReplaysWithoutAnotherVersionIncrement() throws Exception {
        var ticket = create();
        var id = UUID.randomUUID().toString();
        var command = body(id, ticket.version());
        mvc.perform(post("/api/tickets/{id}/notes", ticket.id()).with(jwt().jwt(j -> j.subject("trusted-agent"))
            .authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT")))
            .header("X-Actor-Subject", "spoofed").contentType(MediaType.APPLICATION_JSON).content(command))
            .andExpect(status().isOk()).andExpect(jsonPath("content").value("已核对合成订单，请财务复核。"));
        assertThat(notes.findByTicketIdAndRequestId(ticket.id(), id).orElseThrow().getAuthorSubject()).isEqualTo("trusted-agent");
        var version = repository.findById(ticket.id()).orElseThrow().getVersion();
        assertThat(version).isEqualTo(ticket.version() + 1);
        mvc.perform(post("/api/tickets/{id}/notes", ticket.id()).with(jwt().jwt(j -> j.subject("trusted-agent"))
            .authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT")))
            .contentType(MediaType.APPLICATION_JSON).content(command)).andExpect(status().isOk());
        assertThat(repository.findById(ticket.id()).orElseThrow().getVersion()).isEqualTo(version);
        mvc.perform(get("/api/tickets/{id}/notes", ticket.id()).with(jwt().authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT"))))
            .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(1));
    }
    @Test
    void staleCommandDoesNotCreateNote() throws Exception {
        var ticket = create();
        var id = UUID.randomUUID().toString();
        mvc.perform(post("/api/tickets/{id}/notes", ticket.id()).with(jwt().authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT")))
            .contentType(MediaType.APPLICATION_JSON).content(body(id, ticket.version() + 4)))
            .andExpect(status().isConflict()).andExpect(jsonPath("code").value("VERSION_CONFLICT"));
        assertThat(notes.findByTicketIdAndRequestId(ticket.id(), id)).isEmpty();
    }
    @Test
    void closedTicketRejectsNotes() throws Exception {
        var response = create();
        var ticket = repository.findById(response.id()).orElseThrow();
        ticket.setStatus("CLOSED"); repository.saveAndFlush(ticket);
        mvc.perform(post("/api/tickets/{id}/notes", ticket.getId()).with(jwt().authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT")))
            .contentType(MediaType.APPLICATION_JSON).content(body(UUID.randomUUID().toString(), ticket.getVersion())))
            .andExpect(status().isConflict());
        assertThat(notes.findTop100ByTicketIdOrderByCreatedAtDescIdDesc(ticket.getId())).isEmpty();
    }
    @Test
    void rejectsBlankNoteAndClientSuppliedActor() throws Exception {
        var ticket = create();
        mvc.perform(post("/api/tickets/{id}/notes", ticket.id()).with(jwt().authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT")))
            .contentType(MediaType.APPLICATION_JSON).content("{\"noteId\":\"" + UUID.randomUUID() + "\",\"content\":\"  \",\"expectedVersion\":0}"))
            .andExpect(status().isBadRequest());
        mvc.perform(post("/api/tickets/{id}/notes", ticket.id()).with(jwt().authorities(new SimpleGrantedAuthority("ROLE_SUPPORT_AGENT")))
            .contentType(MediaType.APPLICATION_JSON).content(body(UUID.randomUUID().toString(), 0).replace("}", ",\"authorLabel\":\"admin\"}")))
            .andExpect(status().isBadRequest());
    }
    @Test
    void requiresAuthenticationAndSupportRole() throws Exception {
        TestTrustedActors.clear();
        mvc.perform(get("/api/tickets/missing/notes")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/tickets/missing/notes").with(jwt().authorities(new SimpleGrantedAuthority("ROLE_OTHER"))))
            .andExpect(status().isForbidden());
    }
}
