package com.cyagent.supportcopilot.analysis;

import java.util.Objects;

import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Component;

import com.cyagent.supportcopilot.knowledge.KnowledgeAccessException;
import com.cyagent.supportcopilot.knowledge.KnowledgeCorpusStore;

@Component
public class AnalysisResponseAccessPolicy {

	private final KnowledgeAccessProvider accessProvider;
	private final KnowledgeCorpusStore corpusStore;

	public AnalysisResponseAccessPolicy(KnowledgeAccessProvider accessProvider, KnowledgeCorpusStore corpusStore) {
		this.accessProvider = accessProvider;
		this.corpusStore = corpusStore;
	}

	public boolean canRead(AnalysisResponse response) {
		if (response.retrieval().hits().isEmpty()) {
			return "FALLBACK".equals(response.status()) && response.fallbackReason() != null
				&& response.suggestedReply().citations().isEmpty();
		}
		try {
			var access = accessProvider.currentAccess();
			var corpus = corpusStore.load();
			if (!corpus.releaseId().equals(access.releaseId())
				|| corpus.releaseVersion() != access.releaseVersion()
				|| !corpus.corpusChecksum().equals(access.corpusChecksum())) {
				return false;
			}
			// A reply can contain knowledge from every retrieved hit, including uncited hits.
			return response.retrieval().hits().stream().allMatch(hit -> corpus.chunks().stream()
				.anyMatch(chunk -> chunk.chunkId().equals(hit.chunkId())
					&& Objects.equals(chunk.documentId(), hit.documentId())
					&& Objects.equals(chunk.documentTitle(), hit.documentTitle())
					&& Objects.equals(chunk.section(), hit.section())
					&& Objects.equals(chunk.content(), hit.content())
					&& Objects.equals(chunk.sourceUri(), hit.sourceUri())
					&& chunk.allowedScopes().stream().anyMatch(access.allowedScopes()::contains)));
		} catch (KnowledgeAccessException exception) {
			return false;
		}
	}

	public AnalysisResponse requireReadable(AnalysisResponse response) {
		if (!canRead(response)) {
			throw new AccessDeniedException("Current knowledge access does not permit this analysis.");
		}
		return response;
	}
}
