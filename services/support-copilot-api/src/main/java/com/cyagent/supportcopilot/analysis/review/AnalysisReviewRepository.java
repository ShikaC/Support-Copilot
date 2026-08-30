package com.cyagent.supportcopilot.analysis.review;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.transaction.annotation.Transactional;

public interface AnalysisReviewRepository extends JpaRepository<AnalysisReview, String> {

	Optional<AnalysisReview> findFirstByAnalysisIdOrderByCreatedAtDesc(String analysisId);

	List<AnalysisReview> findByAnalysisIdOrderByCreatedAtDesc(String analysisId);

	List<AnalysisReview> findByAnalysisIdInOrderByCreatedAtDescIdDesc(Collection<String> analysisIds);

	long countByActionIn(Collection<AnalysisReviewAction> actions);

	@Transactional
	void deleteAllByTicketId(String ticketId);
}
