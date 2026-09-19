package com.cyagent.supportcopilot.common;

import com.cyagent.supportcopilot.analysis.AnalysisResponse;
import com.cyagent.supportcopilot.analysis.MockAnalysisFactory;
import com.cyagent.supportcopilot.knowledge.KnowledgeCorpusStore;
import com.cyagent.supportcopilot.ticket.Ticket;

public final class CanonicalAnalysisFixture {
	private CanonicalAnalysisFixture() { }

	public static AnalysisResponse create(Ticket ticket, KnowledgeCorpusStore corpus) {
		var base = new MockAnalysisFactory().createMock(ticket);
		var hits = corpus.load().chunks().stream()
			.filter(chunk -> chunk.categories().contains(ticket.getCategory()))
			.map(chunk -> new AnalysisResponse.RetrievalHit(chunk.chunkId(), chunk.documentId(), chunk.documentTitle(),
				chunk.section(), chunk.content(), chunk.sourceUri(), "HYBRID", 1, 1, 1, 1, true))
			.toList();
		if (hits.isEmpty()) throw new IllegalArgumentException("Fixture category needs canonical evidence.");
		return new AnalysisResponse(base.id(), base.traceId(), base.status(), base.mode(), base.fallbackReason(),
			base.modelName(), base.promptVersion(), base.classification(), base.workflowSteps(),
			new AnalysisResponse.Retrieval(base.retrieval().query(), hits), base.suggestedReply(),
			base.decision(), base.usage(), base.createdAt());
	}
}
