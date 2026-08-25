package com.cyagent.supportcopilot.analysis;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import org.junit.jupiter.api.Test;

class AnalysisSingleFlightCoordinatorTests {

	private final AnalysisSingleFlightCoordinator coordinator = new AnalysisSingleFlightCoordinator();

	@Test
	void concurrentRequestsForTheSameAnalysisShareOneExecution() throws Exception {
		// Given: the first analysis owns the business key and remains in progress.
		var executionStarted = new CountDownLatch(1);
		var secondCallerStarted = new CountDownLatch(1);
		var releaseExecution = new CountDownLatch(1);
		var executions = new AtomicInteger();
		var response = response("analysis-shared", "trace-owner");

		try (var executor = Executors.newFixedThreadPool(2)) {
			var first = executor.submit(() -> coordinator.execute(
				"ticket-10042",
				3,
				"ticket-analysis-v1",
				() -> {
					executions.incrementAndGet();
					executionStarted.countDown();
					await(releaseExecution);
					return response;
				}
			));
			assertThat(executionStarted.await(1, TimeUnit.SECONDS)).isTrue();

			// When: a second caller submits the same ticket, version, and policy.
			var second = executor.submit(() -> {
				secondCallerStarted.countDown();
				return coordinator.execute(
					"ticket-10042",
					3,
					"ticket-analysis-v1",
					() -> {
						executions.incrementAndGet();
						return response("analysis-duplicate", "trace-duplicate");
					}
				);
			});
			assertThat(secondCallerStarted.await(1, TimeUnit.SECONDS)).isTrue();
			assertThatThrownBy(() -> second.get(100, TimeUnit.MILLISECONDS))
				.isInstanceOf(java.util.concurrent.TimeoutException.class);
			releaseExecution.countDown();

			// Then: both callers receive the owner's result and only one execution runs.
			var firstResult = first.get(1, TimeUnit.SECONDS);
			var secondResult = second.get(1, TimeUnit.SECONDS);
			assertThat(firstResult.response()).isSameAs(response);
			assertThat(firstResult.joined()).isFalse();
			assertThat(secondResult.response()).isSameAs(response);
			assertThat(secondResult.joined()).isTrue();
			assertThat(executions).hasValue(1);
		}
	}

	@Test
	void completedAnalysisReleasesTheKeyForAnExplicitRetry() {
		// Given: one analysis for the business key has completed.
		var executions = new AtomicInteger();
		var first = coordinator.execute(
			"ticket-10042",
			3,
			"ticket-analysis-v1",
			() -> response("analysis-first", "trace-first")
		);

		// When: a later request explicitly analyzes the same unchanged input again.
		var second = coordinator.execute(
			"ticket-10042",
			3,
			"ticket-analysis-v1",
			() -> {
				executions.incrementAndGet();
				return response("analysis-retry", "trace-retry");
			}
		);

		// Then: the completed key is not a permanent cache and the retry executes.
		assertThat(first.response().id()).isEqualTo("analysis-first");
		assertThat(first.joined()).isFalse();
		assertThat(second.response().id()).isEqualTo("analysis-retry");
		assertThat(second.joined()).isFalse();
		assertThat(executions).hasValue(1);
	}

	@Test
	void analysisForAnotherTicketDoesNotWaitForTheActiveExecution() throws Exception {
		// Given: one ticket analysis is blocked inside its external operation.
		var firstStarted = new CountDownLatch(1);
		var releaseFirst = new CountDownLatch(1);
		try (var executor = Executors.newFixedThreadPool(2)) {
			var first = executor.submit(() -> coordinator.execute(
				"ticket-10042",
				3,
				"ticket-analysis-v1",
				() -> {
					firstStarted.countDown();
					await(releaseFirst);
					return response("analysis-first-ticket", "trace-first-ticket");
				}
			));
			assertThat(firstStarted.await(1, TimeUnit.SECONDS)).isTrue();

			// When: another ticket starts under a different business key.
			var second = executor.submit(() -> coordinator.execute(
				"ticket-10041",
				3,
				"ticket-analysis-v1",
				() -> response("analysis-second-ticket", "trace-second-ticket")
			));

			// Then: the second ticket completes without waiting for the first one.
			assertThat(second.get(1, TimeUnit.SECONDS).response().id())
				.isEqualTo("analysis-second-ticket");
			releaseFirst.countDown();
			assertThat(first.get(1, TimeUnit.SECONDS).response().id())
				.isEqualTo("analysis-first-ticket");
		}
	}

	@Test
	void failedExecutionReleasesTheKeyForRetry() {
		// Given: the owner fails with an unexpected program error.
		assertThatThrownBy(() -> coordinator.execute(
			"ticket-10042",
			3,
			"ticket-analysis-v1",
			() -> {
				throw new IllegalStateException("simulated owner failure");
			}
		))
			.isInstanceOf(IllegalStateException.class)
			.hasMessage("simulated owner failure");

		// When: a later request retries the same business key.
		var retry = coordinator.execute(
			"ticket-10042",
			3,
			"ticket-analysis-v1",
			() -> response("analysis-after-failure", "trace-after-failure")
		);

		// Then: the failed future is gone and the retry executes normally.
		assertThat(retry.response().id()).isEqualTo("analysis-after-failure");
		assertThat(retry.joined()).isFalse();
	}

	@Test
	void joinedCallerReceivesTheOwnersProgrammingFailure() throws Exception {
		// Given: one owner is active and will fail after another caller joins.
		var ownerStarted = new CountDownLatch(1);
		var joinerStarted = new CountDownLatch(1);
		var releaseOwner = new CountDownLatch(1);
		var failure = new IllegalStateException("simulated shared failure");
		try (var executor = Executors.newFixedThreadPool(2)) {
			var owner = executor.submit(() -> coordinator.execute(
				"ticket-10042",
				3,
				"ticket-analysis-v1",
				() -> {
					ownerStarted.countDown();
					await(releaseOwner);
					throw failure;
				}
			));
			assertThat(ownerStarted.await(1, TimeUnit.SECONDS)).isTrue();
			var joiner = executor.submit(() -> {
				joinerStarted.countDown();
				return coordinator.execute(
					"ticket-10042",
					3,
					"ticket-analysis-v1",
					() -> response("analysis-must-not-run", "trace-must-not-run")
				);
			});
			assertThat(joinerStarted.await(1, TimeUnit.SECONDS)).isTrue();
			assertThatThrownBy(() -> joiner.get(100, TimeUnit.MILLISECONDS))
				.isInstanceOf(java.util.concurrent.TimeoutException.class);

			// When: the owner fails.
			releaseOwner.countDown();

			// Then: the owner and joiner both observe the same underlying program error.
			assertThatThrownBy(() -> owner.get(1, TimeUnit.SECONDS)).hasCause(failure);
			assertThatThrownBy(() -> joiner.get(1, TimeUnit.SECONDS)).hasCause(failure);
		}
	}

	private void await(CountDownLatch latch) {
		try {
			if (!latch.await(1, TimeUnit.SECONDS)) {
				throw new IllegalStateException("Timed out waiting for the test release signal");
			}
		} catch (InterruptedException exception) {
			Thread.currentThread().interrupt();
			throw new IllegalStateException("Interrupted while waiting for the test release signal", exception);
		}
	}

	private AnalysisResponse response(String id, String traceId) {
		var ticket = new com.cyagent.supportcopilot.ticket.Ticket();
		ticket.setId("ticket-10042");
		ticket.setSubject("企业 SSO 登录失败");
		ticket.setDescription("成员无法进入工作区");
		ticket.setLanguage("zh-CN");
		ticket.setCustomerTier("ENTERPRISE");
		ticket.setCategory("ACCOUNT_ACCESS");
		ticket.setPriority("HIGH");
		var base = new MockAnalysisFactory().createMock(ticket);
		return new AnalysisResponse(
			id,
			traceId,
			base.status(),
			base.mode(),
			base.fallbackReason(),
			base.modelName(),
			base.promptVersion(),
			base.classification(),
			base.workflowSteps(),
			base.retrieval(),
			base.suggestedReply(),
			base.decision(),
			base.usage(),
			base.createdAt()
		);
	}
}
