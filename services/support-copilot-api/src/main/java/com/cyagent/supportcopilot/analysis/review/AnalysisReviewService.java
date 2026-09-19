package com.cyagent.supportcopilot.analysis.review;

import java.time.Instant;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

import jakarta.persistence.EntityNotFoundException;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.cyagent.supportcopilot.analysis.AnalysisResponse;
import com.cyagent.supportcopilot.analysis.AnalysisResponseAccessPolicy;
import com.cyagent.supportcopilot.analysis.AnalysisRun;
import com.cyagent.supportcopilot.analysis.AnalysisRunRepository;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewDtos.AnalysisReviewResponse;
import com.cyagent.supportcopilot.identity.TrustedActorProvider;
import com.cyagent.supportcopilot.audit.AuditAction;
import com.cyagent.supportcopilot.audit.AuditEventCommand;
import com.cyagent.supportcopilot.audit.AuditEventRecorder;
import com.cyagent.supportcopilot.audit.AuditMetadata;
import com.cyagent.supportcopilot.audit.AuditTargetType;
import com.cyagent.supportcopilot.ticket.Ticket;
import com.cyagent.supportcopilot.ticket.TicketRepository;
import com.cyagent.supportcopilot.idempotency.CommandIdempotencyCompletion;

@Service
public class AnalysisReviewService {

	private final AnalysisReviewRepository analysisReviewRepository;
	private final AnalysisRunRepository analysisRunRepository;
	private final TicketRepository ticketRepository;
	private final ObjectMapper objectMapper;
	private final TrustedActorProvider trustedActorProvider;
	private final AuditEventRecorder auditEventRecorder;
	private final CommandIdempotencyCompletion idempotencyCompletion;
	private final AnalysisResponseAccessPolicy accessPolicy;

	public AnalysisReviewService(
		AnalysisReviewRepository analysisReviewRepository,
		AnalysisRunRepository analysisRunRepository,
		TicketRepository ticketRepository,
		ObjectMapper objectMapper,
		TrustedActorProvider trustedActorProvider,
		AuditEventRecorder auditEventRecorder,
		CommandIdempotencyCompletion idempotencyCompletion,
		AnalysisResponseAccessPolicy accessPolicy
	) {
		this.analysisReviewRepository = analysisReviewRepository;
		this.analysisRunRepository = analysisRunRepository;
		this.ticketRepository = ticketRepository;
		this.objectMapper = objectMapper;
		this.trustedActorProvider = trustedActorProvider;
		this.auditEventRecorder = auditEventRecorder;
		this.idempotencyCompletion = idempotencyCompletion;
		this.accessPolicy = accessPolicy;
	}

	@Transactional
	public AnalysisReviewResponse review(String ticketId, String analysisId, String replyContent) {
		return reviewBusinessResult(ticketId, analysisId, replyContent);
	}

	@Transactional
	public AnalysisReviewResponse reviewIdempotent(IdempotentAnalysisReview command) {
		var response = reviewBusinessResult(command.ticketId(), command.analysisId(), command.content());
		idempotencyCompletion.complete(command.ownership(), 200, response);
		return response;
	}

	private AnalysisReviewResponse reviewBusinessResult(
		String ticketId,
		String analysisId,
		String replyContent
	) {
		var context = prepareReview(ticketId, analysisId);
		var reviewedReply = replyContent.trim();
		var existing = analysisReviewRepository.findFirstByAnalysisIdOrderByCreatedAtDesc(analysisId);
		if (existing.isPresent()
			&& existing.get().getAction() != AnalysisReviewAction.REJECTED
			&& Objects.equals(existing.get().getReviewedReplyContent(), reviewedReply)) {
			return toResponse(existing.get());
		}

		var originalReply = deserialize(context.run()).suggestedReply().content();
		return saveReview(
			context,
			originalReply.trim().equals(reviewedReply)
				? AnalysisReviewAction.APPROVED
				: AnalysisReviewAction.EDITED,
			originalReply,
			reviewedReply,
			null
		);
	}

	@Transactional
	public AnalysisReviewResponse reject(String ticketId, String analysisId, String reason) {
		return rejectBusinessResult(ticketId, analysisId, reason);
	}

	@Transactional
	public AnalysisReviewResponse rejectIdempotent(IdempotentAnalysisReview command) {
		var response = rejectBusinessResult(command.ticketId(), command.analysisId(), command.content());
		idempotencyCompletion.complete(command.ownership(), 200, response);
		return response;
	}

	private AnalysisReviewResponse rejectBusinessResult(String ticketId, String analysisId, String reason) {
		var normalizedReason = reason.trim();
		if (normalizedReason.isEmpty()) {
			throw new IllegalArgumentException("拒绝原因不能为空");
		}

		var context = prepareReview(ticketId, analysisId);
		var existing = analysisReviewRepository.findFirstByAnalysisIdOrderByCreatedAtDesc(analysisId);
		if (existing.isPresent()
			&& existing.get().getAction() == AnalysisReviewAction.REJECTED
			&& Objects.equals(existing.get().getReason(), normalizedReason)) {
			return toResponse(existing.get());
		}

		return saveReview(
			context,
			AnalysisReviewAction.REJECTED,
			deserialize(context.run()).suggestedReply().content(),
			null,
			normalizedReason
		);
	}

	@Transactional(readOnly = true)
	public Optional<AnalysisReviewResponse> latest(String analysisId) {
		if (!canRead(analysisId)) return Optional.empty();
		return analysisReviewRepository.findFirstByAnalysisIdOrderByCreatedAtDesc(analysisId)
			.map(this::toResponse);
	}

	@Transactional(readOnly = true)
	public Map<String, AnalysisReviewResponse> latestForAnalyses(Collection<String> analysisIds) {
		if (analysisIds.isEmpty()) {
			return Map.of();
		}

		var latestByAnalysis = new HashMap<String, AnalysisReviewResponse>();
		for (var review : analysisReviewRepository.findByAnalysisIdInOrderByCreatedAtDescIdDesc(analysisIds)) {
			if (!latestByAnalysis.containsKey(review.getAnalysisId()) && canRead(review.getAnalysisId())) {
				latestByAnalysis.put(review.getAnalysisId(), toResponse(review));
			}
		}
		return Map.copyOf(latestByAnalysis);
	}

	@Transactional(readOnly = true)
	public List<AnalysisReviewResponse> history(String ticketId, String analysisId) {
		findRun(ticketId, analysisId);
		return analysisReviewRepository.findByAnalysisIdOrderByCreatedAtDesc(analysisId).stream()
			.map(this::toResponse)
			.toList();
	}

	private AnalysisRun findRun(String ticketId, String analysisId) {
		var run = analysisRunRepository.findById(analysisId)
			.orElseThrow(() -> new EntityNotFoundException("分析记录不存在：" + analysisId));
		if (!run.getTicketId().equals(ticketId)) {
			throw new EntityNotFoundException("分析记录不属于工单：" + ticketId);
		}
		accessPolicy.requireReadable(deserialize(run));
		return run;
	}

	public void requireReadable(String ticketId, String analysisId) {
		findRun(ticketId, analysisId);
	}

	private boolean canRead(String analysisId) {
		return analysisRunRepository.findById(analysisId).map(this::deserialize)
			.map(accessPolicy::canRead).orElse(false);
	}

	private ReviewContext prepareReview(String ticketId, String analysisId) {
		var run = findRun(ticketId, analysisId);
		var ticket = ticketRepository.findByIdForUpdate(ticketId)
			.orElseThrow(() -> new EntityNotFoundException("工单不存在：" + ticketId));
		var latestRun = analysisRunRepository.findFirstByTicketIdOrderByCreatedAtDesc(ticketId)
			.orElseThrow(() -> new EntityNotFoundException("工单没有可审核的分析记录：" + ticketId));
		var expectedTicketVersion = run.getSourceTicketVersion() + 1;
		if (!latestRun.getId().equals(analysisId) || ticket.getVersion() != expectedTicketVersion) {
			throw new StaleAnalysisReviewException(
				ticketId,
				analysisId,
				latestRun.getId(),
				expectedTicketVersion,
				ticket.getVersion()
			);
		}
		return new ReviewContext(run, ticket);
	}

	private AnalysisReviewResponse saveReview(
		ReviewContext context,
		AnalysisReviewAction action,
		String originalReply,
		String reviewedReply,
		String reason
	) {
		var actor = trustedActorProvider.currentActor();
		var review = new AnalysisReview();
		review.setId("review-" + UUID.randomUUID());
		review.setTicketId(context.run().getTicketId());
		review.setAnalysisId(context.run().getId());
		review.setAction(action);
		review.setReviewerType(actor.type().name());
		review.setReviewerLabel(actor.displayLabel());
		review.setOriginalReplyContent(originalReply);
		review.setReviewedReplyContent(reviewedReply);
		review.setReason(reason);
		review.setTicketVersion(context.ticket().getVersion());
		review.setTraceId(context.run().getTraceId());
		review.setCreatedAt(Instant.now());
		var saved = analysisReviewRepository.saveAndFlush(review);
		auditEventRecorder.record(new AuditEventCommand(
			auditAction(action),
			AuditTargetType.ANALYSIS_REVIEW,
			saved.getId(),
			context.ticket().getVersion(),
			new AuditMetadata.Review(
				AuditMetadata.ReviewAction.valueOf(action.name()),
				context.run().getSourceTicketVersion(),
				context.run().getId()
			)
		));
		return toResponse(saved);
	}

	private AuditAction auditAction(AnalysisReviewAction action) {
		return switch (action) {
			case APPROVED -> AuditAction.ANALYSIS_REVIEW_APPROVED;
			case EDITED -> AuditAction.ANALYSIS_REVIEW_EDITED;
			case REJECTED -> AuditAction.ANALYSIS_REVIEW_REJECTED;
		};
	}

	private AnalysisResponse deserialize(AnalysisRun run) {
		try {
			return objectMapper.readValue(run.getResponseJson(), AnalysisResponse.class);
		} catch (JacksonException exception) {
			throw new IllegalStateException("Unable to read analysis response " + run.getId(), exception);
		}
	}

	private AnalysisReviewResponse toResponse(AnalysisReview review) {
		return new AnalysisReviewResponse(
			review.getId(),
			review.getTicketId(),
			review.getAnalysisId(),
			review.getAction(),
			review.getReviewerType(),
			review.getReviewerLabel(),
			review.getOriginalReplyContent(),
			review.getReviewedReplyContent(),
			review.getReason(),
			review.getTicketVersion(),
			review.getTraceId(),
			review.getCreatedAt()
		);
	}

	private record ReviewContext(AnalysisRun run, Ticket ticket) {
	}
}
