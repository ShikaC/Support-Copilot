package com.cyagent.supportcopilot.analysis;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

public interface AnalysisRunRepository extends JpaRepository<AnalysisRun, String> {

	Optional<AnalysisRun> findFirstByTicketIdOrderByCreatedAtDesc(String ticketId);

	List<AnalysisRun> findByTicketIdOrderByCreatedAtDesc(String ticketId);
}
