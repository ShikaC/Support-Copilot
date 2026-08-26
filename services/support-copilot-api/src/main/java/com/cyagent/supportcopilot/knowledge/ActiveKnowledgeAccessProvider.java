package com.cyagent.supportcopilot.knowledge;

import java.util.List;

import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import tools.jackson.core.JacksonException;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;

import com.cyagent.supportcopilot.analysis.KnowledgeAccess;
import com.cyagent.supportcopilot.analysis.KnowledgeAccessProvider;

@Component
public class ActiveKnowledgeAccessProvider implements KnowledgeAccessProvider {

	private final KnowledgeActiveReleaseRepository activeRepository;
	private final KnowledgeReleaseRepository releaseRepository;
	private final TrustedSupportScopeProvider trustedScopeProvider;
	private final ObjectMapper objectMapper;

	public ActiveKnowledgeAccessProvider(
		KnowledgeActiveReleaseRepository activeRepository,
		KnowledgeReleaseRepository releaseRepository,
		TrustedSupportScopeProvider trustedScopeProvider,
		ObjectMapper objectMapper
	) {
		this.activeRepository = activeRepository;
		this.releaseRepository = releaseRepository;
		this.trustedScopeProvider = trustedScopeProvider;
		this.objectMapper = objectMapper;
	}

	@Override
	@Transactional(readOnly = true)
	public KnowledgeAccess currentAccess() {
		var pointer = activeRepository.findById(KnowledgeActiveRelease.SINGLETON_ID)
			.orElseThrow(KnowledgeAccessException::inactive);
		var release = releaseRepository.findById(pointer.getReleaseId())
			.orElseThrow(KnowledgeAccessException::inactive);
		if (release.getStatus() != KnowledgeReleaseStatus.PUBLISHED) {
			throw KnowledgeAccessException.inactive();
		}
		var releaseScopes = readScopes(release);
		var trusted = trustedScopeProvider.currentScopes();
		var allowed = releaseScopes.stream().filter(trusted::contains).map(Enum::name).toList();
		return new KnowledgeAccess(
			release.getReleaseId(),
			release.getReleaseVersion(),
			release.getCorpusChecksum(),
			allowed
		);
	}

	private List<KnowledgeScope> readScopes(KnowledgeRelease release) {
		try {
			return KnowledgeScope.canonicalize(objectMapper.readValue(
				release.getAllowedScopesJson(),
				new TypeReference<List<String>>() { }
			));
		} catch (JacksonException exception) {
			throw KnowledgeAccessException.mismatch();
		}
	}
}
