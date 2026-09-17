package com.cyagent.supportcopilot.ticket;

import static com.cyagent.supportcopilot.common.MySqlTestSupport.container;
import static com.cyagent.supportcopilot.common.MySqlTestSupport.createDatabase;
import static com.cyagent.supportcopilot.common.MySqlTestSupport.startContext;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.jdbc.core.JdbcTemplate;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.mysql.MySQLContainer;

import com.cyagent.supportcopilot.analysis.TicketVersionConflictException;
import com.cyagent.supportcopilot.common.TestTrustedActors;
import com.cyagent.supportcopilot.ticket.TicketNoteController.CreateNoteRequest;
import com.cyagent.supportcopilot.ticket.TicketNoteController.NoteResponse;

@EnabledIfEnvironmentVariable(named = "SUPPORT_COPILOT_RUN_MYSQL_TESTS", matches = "true")
@Testcontainers
class TicketNoteMySqlIntegrationTests {
    @Container
    static final MySQLContainer MYSQL = container("support_copilot_ticket_notes");

    @Test
    void concurrentReplayPersistsOneNoteAndAuditAcrossApplicationRestart() throws Exception {
        var database = createDatabase(MYSQL, "ticket_note_replay");
        String ticketId;
        long initialVersion;
        NoteResponse original;
        var requestId = UUID.randomUUID().toString();
        try (var first = startContext(database); var second = startContext(database)) {
            var ticket = create(first);
            ticketId = ticket.id();
            initialVersion = ticket.version();
            var command = new CreateNoteRequest(requestId, "Synthetic internal follow-up", initialVersion);
            var gate = new StartGate(new CountDownLatch(2), new CountDownLatch(1));
            try (var executor = Executors.newFixedThreadPool(2)) {
                var one = executor.submit(() -> concurrentAdd(first, ticket.id(), command, gate));
                var two = executor.submit(() -> concurrentAdd(second, ticket.id(), command, gate));
                assertThat(gate.ready().await(10, TimeUnit.SECONDS)).isTrue();
                gate.start().countDown();
                original = one.get(15, TimeUnit.SECONDS);
                assertThat(two.get(15, TimeUnit.SECONDS)).usingRecursiveComparison()
                    .ignoringFields("createdAt").isEqualTo(original);
            }
            assertPersisted(first, ticketId, initialVersion + 1, original.id());
        }
        try (var restarted = startContext(database)) {
            var replay = add(restarted, ticketId,
                new CreateNoteRequest(requestId, "Synthetic internal follow-up", initialVersion));
            assertThat(replay).usingRecursiveComparison().ignoringFields("createdAt").isEqualTo(original);
            assertPersisted(restarted, ticketId, initialVersion + 1, original.id());
            assertThatThrownBy(() -> add(restarted, ticketId,
                new CreateNoteRequest(requestId, "Conflicting content", initialVersion)))
                .isInstanceOf(TicketVersionConflictException.class);
            assertPersisted(restarted, ticketId, initialVersion + 1, original.id());
        }
    }

    @Test
    void sameRequestIdOnDifferentTicketsCreatesIndependentNotes() throws Exception {
        var database = createDatabase(MYSQL, "ticket_note_scope");
        try (var first = startContext(database); var second = startContext(database)) {
            var left = create(first);
            var right = create(second);
            var requestId = UUID.randomUUID().toString();
            var gate = new StartGate(new CountDownLatch(2), new CountDownLatch(1));
            try (var executor = Executors.newFixedThreadPool(2)) {
                var one = executor.submit(() -> concurrentAdd(first, left.id(),
                    new CreateNoteRequest(requestId, "Left note", left.version()), gate));
                var two = executor.submit(() -> concurrentAdd(second, right.id(),
                    new CreateNoteRequest(requestId, "Right note", right.version()), gate));
                assertThat(gate.ready().await(10, TimeUnit.SECONDS)).isTrue();
                gate.start().countDown();
                var leftNote = one.get(15, TimeUnit.SECONDS);
                var rightNote = two.get(15, TimeUnit.SECONDS);
                assertThat(leftNote.id()).isNotEqualTo(rightNote.id());
                assertPersisted(first, left.id(), left.version() + 1, leftNote.id());
                assertPersisted(second, right.id(), right.version() + 1, rightNote.id());
            }
        }
    }

    private TicketDtos.TicketResponse create(ConfigurableApplicationContext context) {
        TestTrustedActors.authenticate("mysql-note-agent", "SUPPORT_AGENT");
        try {
            return context.getBean(TicketService.class).create(new TicketDtos.CreateTicketRequest(
                TicketDomain.Channel.EMAIL, "Synthetic customer", "Note verification",
                TicketDomain.CustomerTier.STANDARD, "MySQL note verification", "Synthetic content", "en-US"));
        } finally {
            TestTrustedActors.clear();
        }
    }

    private NoteResponse concurrentAdd(ConfigurableApplicationContext context, String ticketId,
        CreateNoteRequest request, StartGate gate) throws Exception {
        gate.ready().countDown();
        if (!gate.start().await(10, TimeUnit.SECONDS)) throw new IllegalStateException("Notes were not released");
        return add(context, ticketId, request);
    }

    private NoteResponse add(ConfigurableApplicationContext context, String ticketId, CreateNoteRequest request) {
        TestTrustedActors.authenticate("mysql-note-agent", "SUPPORT_AGENT");
        try {
            return context.getBean(TicketNoteService.class).add(ticketId, request);
        } finally {
            TestTrustedActors.clear();
        }
    }

    private void assertPersisted(ConfigurableApplicationContext context, String ticketId, long version, String noteId) {
        assertThat(context.getBean(TicketRepository.class).findById(ticketId).orElseThrow().getVersion()).isEqualTo(version);
        assertThat(context.getBean(TicketNoteService.class).list(ticketId)).extracting(NoteResponse::id).containsExactly(noteId);
        var jdbc = context.getBean(JdbcTemplate.class);
        var audit = jdbc.queryForList("select actor_subject, metadata_json from audit_events "
            + "where target_id = ? and action = 'TICKET_NOTE_ADDED'", ticketId);
        assertThat(audit).hasSize(1);
        assertThat(audit.getFirst().get("actor_subject")).isEqualTo("mysql-note-agent");
        assertThat(audit.getFirst().get("metadata_json").toString()).contains(noteId).doesNotContain("Synthetic internal follow-up");
    }

    private record StartGate(CountDownLatch ready, CountDownLatch start) {}
}
