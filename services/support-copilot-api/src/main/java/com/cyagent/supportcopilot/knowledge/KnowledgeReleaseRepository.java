package com.cyagent.supportcopilot.knowledge;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

public interface KnowledgeReleaseRepository extends JpaRepository<KnowledgeRelease, String> {
	Optional<KnowledgeRelease> findByReleaseVersion(int releaseVersion);
	List<KnowledgeRelease> findAllByOrderByReleaseVersionDesc();
}
