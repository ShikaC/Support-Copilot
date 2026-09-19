package com.cyagent.supportcopilot.analysis.review;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import com.cyagent.supportcopilot.analysis.AnalysisPersistenceService;
import com.cyagent.supportcopilot.analysis.AnalysisResponse;
import com.cyagent.supportcopilot.analysis.AnalysisRunRepository;
import com.cyagent.supportcopilot.ticket.Ticket;
import com.cyagent.supportcopilot.ticket.TicketRepository;
import com.cyagent.supportcopilot.ticket.TicketService;

@SpringBootTest
@ActiveProfiles("test")
class AnalysisReviewServiceTests {

	@Autowired
	private AnalysisReviewService analysisReviewService;

	@Test
	void reviewPersistsTheAuthenticatedJwtSubject() {
		// Given: an analysis that can be reviewed through the secured test policy.
		var analysis = saveAnalysis();

		// When: the authenticated reviewer approves the reply.
		var review = analysisReviewService.review(
			ticketId,
			analysis.id(),
			analysis.suggestedReply().content()
		);

		// Then: the persisted actor is derived from the JWT subject.
		assertThat(review.reviewerType()).isEqualTo("AUTHENTICATED_JWT");
		assertThat(review.reviewerLabel()).isEqualTo("service-test-reviewer");
	}

	@Autowired
	private AnalysisReviewRepository analysisReviewRepository;

	@Autowired
	private AnalysisPersistenceService analysisPersistenceService;

	@Autowired
	private AnalysisRunRepository analysisRunRepository;

	@Autowired
	private com.cyagent.supportcopilot.knowledge.KnowledgeCorpusStore corpus;

	@Autowired
	private TicketRepository ticketRepository;

	@Autowired
	private TicketService ticketService;

	@Autowired
	private PlatformTransactionManager transactionManager;

	private String ticketId;

	@BeforeEach
	void authenticateReviewer() {
		AnalysisReviewTestFixture.authenticateReviewer();
	}

	@AfterEach
	void cleanUp() {
		if (ticketId != null) {
			analysisReviewRepository.deleteAllByTicketId(ticketId);
			analysisRunRepository.findByTicketIdOrderByCreatedAtDesc(ticketId)
				.forEach(analysisRunRepository::delete);
			ticketRepository.deleteById(ticketId);
		}
		AnalysisReviewTestFixture.clearAuthentication();
	}

	@Test
	void recordsApprovalWhenReplyIsUnchanged() {
		var analysis = saveAnalysis();

		var review = analysisReviewService.review(
			ticketId,
			analysis.id(),
			analysis.suggestedReply().content()
		);

		assertThat(review.action()).isEqualTo(AnalysisReviewAction.APPROVED);
		assertThat(review.reviewerType()).isEqualTo("AUTHENTICATED_JWT");
		assertThat(review.traceId()).isEqualTo(analysis.traceId());
		assertThat(analysisReviewRepository.findById(review.id())).isPresent();
	}

	@Test
	void recordsOriginalAndEditedReply() {
		var analysis = saveAnalysis();
		var editedReply = analysis.suggestedReply().content() + "\n我们会在核验后同步处理进展。";

		var review = analysisReviewService.review(ticketId, analysis.id(), editedReply);

		assertThat(review.action()).isEqualTo(AnalysisReviewAction.EDITED);
		assertThat(review.originalReplyContent()).isEqualTo(analysis.suggestedReply().content());
		assertThat(review.reviewedReplyContent()).isEqualTo(editedReply);
	}

	@Test
	void recordsRejectionReasonWithoutTreatingTheSuggestionAsReviewedContent() {
		var analysis = saveAnalysis();

		var review = analysisReviewService.reject(
			ticketId,
			analysis.id(),
			"退款结论需要先核对支付流水"
		);

		assertThat(review.action()).isEqualTo(AnalysisReviewAction.REJECTED);
		assertThat(review.originalReplyContent()).isEqualTo(analysis.suggestedReply().content());
		assertThat(review.reviewedReplyContent()).isNull();
		assertThat(review.reason()).isEqualTo("退款结论需要先核对支付流水");
		assertThat(analysisReviewRepository.findById(review.id())).isPresent();
	}

	@Test
	void returnsExistingRejectionWhenTheSameReasonIsRetried() {
		var analysis = saveAnalysis();

		var first = analysisReviewService.reject(ticketId, analysis.id(), "证据不足");
		var retry = analysisReviewService.reject(ticketId, analysis.id(), "证据不足");

		assertThat(retry.id()).isEqualTo(first.id());
		assertThat(analysisReviewRepository.findByAnalysisIdOrderByCreatedAtDesc(analysis.id()))
			.hasSize(1);
	}

	@Test
	void preservesRejectionReasonInTheRefreshedTicketEvent() {
		var analysis = saveAnalysis();
		var review = analysisReviewService.reject(ticketId, analysis.id(), "证据不足");

		var ticket = ticketService.get(ticketId);

		assertThat(ticket.events())
			.filteredOn(event -> event.id().equals(review.id()))
			.singleElement()
			.extracting(event -> event.detail())
			.isEqualTo("service-test-reviewer已拒绝回复建议：证据不足");
	}

	@Test
	void returnsExistingReviewWhenTheSameContentIsRetried() {
		var analysis = saveAnalysis();

		var first = analysisReviewService.review(
			ticketId,
			analysis.id(),
			analysis.suggestedReply().content()
		);
		var retry = analysisReviewService.review(
			ticketId,
			analysis.id(),
			analysis.suggestedReply().content()
		);

		assertThat(retry.id()).isEqualTo(first.id());
		assertThat(analysisReviewRepository.findByAnalysisIdOrderByCreatedAtDesc(analysis.id()))
			.hasSize(1);
	}

	@Test
	void rejectsReviewWhenTicketChangedAfterAnalysis() {
		var analysis = saveAnalysis();
		var changedTicket = ticketRepository.findById(ticketId).orElseThrow();
		changedTicket.setStatus("IN_PROGRESS");
		ticketRepository.saveAndFlush(changedTicket);

		assertThatThrownBy(() -> analysisReviewService.review(
			ticketId,
			analysis.id(),
			analysis.suggestedReply().content()
		))
			.isInstanceOf(StaleAnalysisReviewException.class);
		assertThat(analysisReviewRepository.findByAnalysisIdOrderByCreatedAtDesc(analysis.id()))
			.isEmpty();
	}

	@Test
	void rejectsSameContentRetryWhenTicketChangedAfterReview() {
		var analysis = saveAnalysis();
		analysisReviewService.review(ticketId, analysis.id(), analysis.suggestedReply().content());
		var changedTicket = ticketRepository.findById(ticketId).orElseThrow();
		changedTicket.setStatus("IN_PROGRESS");
		ticketRepository.saveAndFlush(changedTicket);

		assertThatThrownBy(() -> analysisReviewService.review(
			ticketId,
			analysis.id(),
			analysis.suggestedReply().content()
		))
			.isInstanceOf(StaleAnalysisReviewException.class);
		assertThat(analysisReviewRepository.findByAnalysisIdOrderByCreatedAtDesc(analysis.id()))
			.hasSize(1);
	}

	@Test
	void rejectsRejectionWhenTicketChangedAfterAnalysis() {
		var analysis = saveAnalysis();
		var changedTicket = ticketRepository.findById(ticketId).orElseThrow();
		changedTicket.setStatus("IN_PROGRESS");
		ticketRepository.saveAndFlush(changedTicket);

		assertThatThrownBy(() -> analysisReviewService.reject(ticketId, analysis.id(), "版本已变化"))
			.isInstanceOf(StaleAnalysisReviewException.class);
		assertThat(analysisReviewRepository.findByAnalysisIdOrderByCreatedAtDesc(analysis.id()))
			.isEmpty();
	}

	@Test
	void waitsForConcurrentTicketUpdateBeforeCheckingReviewVersion() throws Exception {
		var analysis = saveAnalysis();
		var lockAcquired = new CountDownLatch(1);
		var releaseUpdate = new CountDownLatch(1);
		var executor = Executors.newFixedThreadPool(2);

		try {
			var updateFuture = executor.submit(() -> new TransactionTemplate(transactionManager)
				.executeWithoutResult(status -> {
					var ticket = ticketRepository.findByIdForUpdate(ticketId).orElseThrow();
					lockAcquired.countDown();
					await(releaseUpdate);
					ticket.setStatus("IN_PROGRESS");
				}));
			assertThat(lockAcquired.await(2, TimeUnit.SECONDS)).isTrue();

			var reviewFuture = executor.submit(() -> {
				AnalysisReviewTestFixture.authenticateReviewer();
				try {
					analysisReviewService.review(
						ticketId,
						analysis.id(),
						analysis.suggestedReply().content()
					);
					return null;
				} catch (RuntimeException exception) {
					return exception;
				} finally {
					AnalysisReviewTestFixture.clearAuthentication();
				}
			});
			assertThatThrownBy(() -> reviewFuture.get(200, TimeUnit.MILLISECONDS))
				.isInstanceOf(TimeoutException.class);

			releaseUpdate.countDown();
			updateFuture.get(2, TimeUnit.SECONDS);
			assertThat(reviewFuture.get(2, TimeUnit.SECONDS))
				.isInstanceOf(StaleAnalysisReviewException.class);
		} finally {
			releaseUpdate.countDown();
			executor.shutdownNow();
		}
	}

	private void await(CountDownLatch latch) {
		try {
			latch.await();
		} catch (InterruptedException exception) {
			Thread.currentThread().interrupt();
			throw new IllegalStateException("Interrupted while coordinating review test", exception);
		}
	}

	private AnalysisResponse saveAnalysis() {
		var ticket = saveTicket();
		var analysis = com.cyagent.supportcopilot.common.CanonicalAnalysisFixture.create(ticket, corpus);
		analysisPersistenceService.persist(ticket.getId(), ticket.getVersion(), analysis);
		return analysis;
	}

	private Ticket saveTicket() {
		var ticket = AnalysisReviewTestFixture.ticket();
		ticketId = ticket.getId();
		return ticketRepository.saveAndFlush(ticket);
	}
}
