package com.cyagent.supportcopilot.knowledge;

import java.time.Instant;
import java.util.Arrays;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

@Component
public class KnowledgeBaselineInitializer implements ApplicationRunner {

	private final KnowledgeReleaseRepository releaseRepository;
	private final KnowledgeActiveReleaseRepository activeRepository;
	private final ObjectMapper objectMapper;
	private final KnowledgeCorpusStore corpusStore;
	private final String releaseId;
	private final int releaseVersion;
	private final String corpusChecksum;

	public KnowledgeBaselineInitializer(
		KnowledgeReleaseRepository releaseRepository,
		KnowledgeActiveReleaseRepository activeRepository,
		ObjectMapper objectMapper,
		KnowledgeCorpusStore corpusStore,
		@Value("${support-copilot.knowledge.baseline.release-id}") String releaseId,
		@Value("${support-copilot.knowledge.baseline.release-version}") int releaseVersion,
		@Value("${support-copilot.knowledge.baseline.corpus-checksum}") String corpusChecksum
	) {
		this.releaseRepository = releaseRepository;
		this.activeRepository = activeRepository;
		this.objectMapper = objectMapper;
		this.corpusStore = corpusStore;
		this.releaseId = releaseId;
		this.releaseVersion = releaseVersion;
		this.corpusChecksum = corpusChecksum;
	}

	@Override
	@Transactional
	public void run(ApplicationArguments args) {
		var corpus = corpusStore.load();
		if (activeRepository.existsById(KnowledgeActiveRelease.SINGLETON_ID)) {
			var active = activeRepository.findById(KnowledgeActiveRelease.SINGLETON_ID)
				.orElseThrow(KnowledgeAccessException::inactive);
			var release = releaseRepository.findById(active.getReleaseId())
				.orElseThrow(KnowledgeAccessException::inactive);
			if (release.getStatus() != KnowledgeReleaseStatus.PUBLISHED) {
				throw KnowledgeAccessException.inactive();
			}
			if (!matches(corpus, release)) {
				throw KnowledgeAccessException.mismatch();
			}
			return;
		}
		if (!corpus.releaseId().equals(releaseId)
			|| corpus.releaseVersion() != releaseVersion
			|| !corpus.corpusChecksum().equals(corpusChecksum)) {
			throw KnowledgeAccessException.mismatch();
		}
		var release = releaseRepository.findById(releaseId).orElseGet(this::baseline);
		if (release.getStatus() != KnowledgeReleaseStatus.PUBLISHED) {
			throw KnowledgeAccessException.inactive();
		}
		if (!matches(corpus, release)) {
			throw KnowledgeAccessException.mismatch();
		}
		activeRepository.save(new KnowledgeActiveRelease(releaseId));
	}

	private boolean matches(KnowledgeCorpusStore.KnowledgeCorpus corpus, KnowledgeRelease release) {
		return corpus.releaseId().equals(release.getReleaseId())
			&& corpus.releaseVersion() == release.getReleaseVersion()
			&& corpus.corpusChecksum().equals(release.getCorpusChecksum());
	}

	private KnowledgeRelease baseline() {
		if (releaseId.isBlank() || releaseVersion <= 0 || !corpusChecksum.matches("[a-f0-9]{64}")) {
			throw KnowledgeAccessException.mismatch();
		}
		var now = Instant.now();
		var release = new KnowledgeRelease(
			releaseId,
			releaseVersion,
			corpusChecksum,
			serializeAllScopes(),
			"bundled-system",
			now
		);
		release.approve("bundled-system", now);
		release.publish("bundled-system", now);
		return releaseRepository.save(release);
	}

	private String serializeAllScopes() {
		try {
			return objectMapper.writeValueAsString(
				Arrays.stream(KnowledgeScope.values()).map(Enum::name).toList()
			);
		} catch (JacksonException exception) {
			throw new IllegalStateException("Unable to serialize baseline knowledge scopes.", exception);
		}
	}
}
