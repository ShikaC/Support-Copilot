package com.cyagent.supportcopilot.knowledge;

import java.util.Optional;

import jakarta.persistence.LockModeType;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;

public interface KnowledgeActiveReleaseRepository extends JpaRepository<KnowledgeActiveRelease, String> {

	@Lock(LockModeType.PESSIMISTIC_WRITE)
	@Query("select active from KnowledgeActiveRelease active where active.id = 'active'")
	Optional<KnowledgeActiveRelease> findForUpdate();
}
