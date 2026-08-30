package com.cyagent.supportcopilot.knowledge;

import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Set;

import org.springframework.stereotype.Service;

import com.cyagent.supportcopilot.analysis.KnowledgeAccessProvider;

@Service
public class KnowledgeService {

	private final KnowledgeAccessProvider knowledgeAccessProvider;
	private final KnowledgeCorpusStore corpusStore;

	public KnowledgeService(
		KnowledgeAccessProvider knowledgeAccessProvider,
		KnowledgeCorpusStore corpusStore
	) {
		this.knowledgeAccessProvider = knowledgeAccessProvider;
		this.corpusStore = corpusStore;
	}

	public List<KnowledgeHit> search(String query, int topK) {
		var normalized = query == null ? "" : query.toLowerCase(Locale.ROOT);
		var access = knowledgeAccessProvider.currentAccess();
		var corpus = corpusStore.load();
		if (!corpus.releaseId().equals(access.releaseId())
			|| corpus.releaseVersion() != access.releaseVersion()
			|| !corpus.corpusChecksum().equals(access.corpusChecksum())) {
			throw KnowledgeAccessException.mismatch();
		}
		var allowedScopes = Set.copyOf(access.allowedScopes());
		return corpus.chunks().stream()
			.filter(chunk -> chunk.allowedScopes().stream().anyMatch(allowedScopes::contains))
			.map(chunk -> toHit(chunk, score(chunk, normalized)))
			.sorted(Comparator.comparingDouble(KnowledgeHit::score).reversed()
				.thenComparing(KnowledgeHit::chunkId))
			.limit(Math.max(1, Math.min(topK, 10)))
			.toList();
	}

	private KnowledgeHit toHit(KnowledgeCorpusStore.KnowledgeChunk chunk, double score) {
		return new KnowledgeHit(
			chunk.chunkId(),
			chunk.documentTitle(),
			chunk.section(),
			chunk.content(),
			documentType(chunk),
			score
		);
	}

	private double score(KnowledgeCorpusStore.KnowledgeChunk chunk, String query) {
		var text = String.join(
			" ",
			chunk.chunkId(),
			chunk.documentId(),
			chunk.documentTitle(),
			chunk.section(),
			chunk.content(),
			String.join(" ", chunk.keywords())
		).toLowerCase(Locale.ROOT);
		if (query.isBlank()) return 0.5;
		if (text.contains(query)) return 0.99;
		var matches = query.codePoints().filter(codePoint -> text.indexOf(codePoint) >= 0).count();
		return Math.min(0.99, 0.55 + matches * 0.015);
	}

	private String documentType(KnowledgeCorpusStore.KnowledgeChunk chunk) {
		var identity = (chunk.documentId() + " " + chunk.documentTitle()).toLowerCase(Locale.ROOT);
		if (identity.contains("policy") || identity.contains("政策")) return "POLICY";
		if (identity.contains("runbook") || identity.contains("手册")) return "RUNBOOK";
		if (identity.contains("error") || identity.contains("错误")) return "FAQ";
		return "PRODUCT_GUIDE";
	}

	public record KnowledgeHit(
		String chunkId,
		String documentTitle,
		String section,
		String content,
		String documentType,
		double score
	) { }
}
