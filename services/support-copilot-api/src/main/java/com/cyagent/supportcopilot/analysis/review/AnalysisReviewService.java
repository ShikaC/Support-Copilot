package com.cyagent.supportcopilot.analysis.review;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

import jakarta.persistence.EntityNotFoundException;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.cyagent.supportcopilot.analysis.AnalysisResponse;
import com.cyagent.supportcopilot.analysis.AnalysisRun;
import com.cyagent.supportcopilot.analysis.AnalysisRunRepository;
import com.cyagent.supportcopilot.analysis.review.AnalysisReviewDtos.AnalysisReviewResponse;
import com.cyagent.supportcopilot.ticket.TicketRepository;

@Service
public class AnalysisReviewService {

	private static final String REVIEWER_TYPE = "UNAUTHENTICATED_DEMO";
	private static final String REVIEWER_LABEL = "演示管理员";

	private final AnalysisReviewRepository analysisReviewRepository;
	private final AnalysisRunRepository analysisRunRepository;
	private final TicketRepository ticketRepository;
	private final ObjectMapper objectMapper;

	public AnalysisReviewService(
		AnalysisReviewRepository analysisReviewRepository,
		AnalysisRunRepository analysisRunRepository,
		TicketRepository ticketRepository,
		ObjectMapper objectMapper
	) {
		this.analysisReviewRepository = analysisReviewRepository;
		this.analysisRunRepository = analysisRunRepository;
		this.ticketRepository = ticketRepository;
		this.objectMapper = objectMapper;
	}

	@Transactional
	public AnalysisReviewResponse review(String ticketId, String analysisId, String replyContent) {
		var run = findRun(ticketId, analysisId);
		var reviewedReply = replyContent.trim();
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

		var existing = analysisReviewRepository.findFirstByAnalysisIdOrderByCreatedAtDesc(analysisId);
		if (existing.isPresent() && existing.get().getReviewedReplyContent().equals(reviewedReply)) {
			return toResponse(existing.get());
		}

		var originalReply = deserialize(run).suggestedReply().content();
		var review = new AnalysisReview();
		review.setId("review-" + UUID.randomUUID());
		review.setTicketId(ticketId);
		review.setAnalysisId(analysisId);
		review.setAction(originalReply.trim().equals(reviewedReply)
			? AnalysisReviewAction.APPROVED
			: AnalysisReviewAction.EDITED);
		review.setReviewerType(REVIEWER_TYPE);
		review.setReviewerLabel(REVIEWER_LABEL);
		review.setOriginalReplyContent(originalReply);
		review.setReviewedReplyContent(reviewedReply);
		review.setTicketVersion(ticket.getVersion());
		review.setTraceId(run.getTraceId());
		review.setCreatedAt(Instant.now());
		return toResponse(analysisReviewRepository.save(review));
	}

	@Transactional(readOnly = true)
	public Optional<AnalysisReviewResponse> latest(String analysisId) {
		return analysisReviewRepository.findFirstByAnalysisIdOrderByCreatedAtDesc(analysisId)
			.map(this::toResponse);
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
		return run;
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
			review.getTicketVersion(),
			review.getTraceId(),
			review.getCreatedAt()
		);
	}
}
