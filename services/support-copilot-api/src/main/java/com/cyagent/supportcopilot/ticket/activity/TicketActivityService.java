package com.cyagent.supportcopilot.ticket.activity;

import java.time.Instant;
import java.util.Base64;
import java.util.stream.Collectors;

import jakarta.persistence.EntityNotFoundException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

import com.cyagent.supportcopilot.audit.AuditAction;
import com.cyagent.supportcopilot.audit.AuditChangedField;
import com.cyagent.supportcopilot.audit.AuditEvent;
import com.cyagent.supportcopilot.audit.AuditMetadata;
import com.cyagent.supportcopilot.identity.TrustedActorProvider.TrustedActorType;
import com.cyagent.supportcopilot.ticket.TicketQueryException;
import com.cyagent.supportcopilot.ticket.TicketRepository;
import com.cyagent.supportcopilot.ticket.activity.TicketActivityController.ActivityItem;
import com.cyagent.supportcopilot.ticket.activity.TicketActivityController.ActivityPage;

@Service
public class TicketActivityService {
    private final TicketRepository tickets;
    private final TicketActivityRepository activity;
    private final ObjectMapper mapper;

    public TicketActivityService(TicketRepository tickets, TicketActivityRepository activity, ObjectMapper mapper) {
        this.tickets = tickets;
        this.activity = activity;
        this.mapper = mapper;
    }

    @Transactional(readOnly = true)
    public ActivityPage list(String ticketId, String rawCursor, int limit) {
        if (limit < 1 || limit > 100) throw TicketQueryException.invalidPageSize();
        var cursor = parseCursor(ticketId, rawCursor);
        if (!tickets.existsById(ticketId)) throw new EntityNotFoundException("工单不存在：" + ticketId);
        var events = activity.list(ticketId, cursor, limit + 1);
        var hasNext = events.size() > limit;
        var page = hasNext ? events.subList(0, limit) : events;
        var nextCursor = hasNext ? encodeCursor(new Cursor(ticketId, page.getLast().getCreatedAt(), page.getLast().getId())) : null;
        return new ActivityPage(page.stream().map(this::toItem).toList(), nextCursor);
    }

    private Cursor parseCursor(String ticketId, String raw) {
        if (raw == null) return null;
        if (raw.isBlank() || raw.length() > 1024) throw TicketQueryException.invalidCursor();
        try {
            var cursor = mapper.readValue(Base64.getUrlDecoder().decode(raw), Cursor.class);
            if (cursor == null || !ticketId.equals(cursor.ticketId()) || cursor.createdAt() == null || cursor.id() == null
                || !cursor.id().matches("[A-Za-z0-9][A-Za-z0-9._:-]{0,63}")) {
                throw TicketQueryException.invalidCursor();
            }
            return cursor;
        } catch (JacksonException | IllegalArgumentException exception) {
            throw TicketQueryException.invalidCursor();
        }
    }

    private String encodeCursor(Cursor cursor) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(mapper.writeValueAsBytes(cursor));
    }

    private ActivityItem toItem(AuditEvent event) {
        try {
            var action = AuditAction.valueOf(event.getAction());
            var actorLabel = switch (TrustedActorType.valueOf(event.getActorType())) {
                case UNAUTHENTICATED_DEMO -> "匿名演示操作人";
                case AUTHENTICATED_JWT -> "已认证操作人";
            };
            return new ActivityItem(event.getId(), action, actorLabel, event.getCreatedAt(),
                event.getTraceId(), event.getTargetVersion(), detail(action, event.getMetadataJson()));
        } catch (JacksonException | IllegalArgumentException exception) {
            throw new IllegalStateException("Unable to read controlled ticket activity data.", exception);
        }
    }

    private String detail(AuditAction action, String metadata) {
        return switch (action) {
            case TICKET_CREATED -> "创建工单";
            case TICKET_UPDATED -> "更新" + mapper.readValue(metadata, AuditMetadata.TicketChange.class)
                .changedFields().stream().map(this::fieldLabel).collect(Collectors.joining("、"));
            case TICKET_UNASSIGNED -> "取消负责人，放回待领取队列";
            case TICKET_NOTE_ADDED -> "添加内部备注";
            case ANALYSIS_PERSISTED -> analysisDetail(mapper.readValue(metadata, AuditMetadata.Analysis.class));
            case ANALYSIS_REVIEW_APPROVED -> "采纳 AI 回复建议并保存审核记录";
            case ANALYSIS_REVIEW_EDITED -> "修改 AI 回复建议并保存审核记录";
            case ANALYSIS_REVIEW_REJECTED -> "拒绝 AI 回复建议并保存审核记录";
            case KNOWLEDGE_RELEASE_DRAFT_CREATED, KNOWLEDGE_RELEASE_APPROVED,
                KNOWLEDGE_RELEASE_PUBLISHED, KNOWLEDGE_RELEASE_ROLLED_BACK ->
                throw new IllegalStateException("Knowledge events do not belong to ticket activity.");
        };
    }

    private String analysisDetail(AuditMetadata.Analysis analysis) {
        return switch (analysis.mode()) {
            case MOCK -> "完成离线模拟分析";
            case LIVE -> "完成模型分析";
            case FALLBACK -> "分析依赖降级，结果待人工处理";
        };
    }

    private String fieldLabel(AuditChangedField field) {
        return switch (field) {
            case ASSIGNEE -> "负责人";
            case CATEGORY -> "分类";
            case PRIORITY -> "优先级";
            case STATUS -> "状态";
        };
    }

    record Cursor(String ticketId, Instant createdAt, String id) {}
}
