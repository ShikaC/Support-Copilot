package com.cyagent.supportcopilot.knowledge;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.cyagent.supportcopilot.knowledge.KnowledgeService.KnowledgeHit;

@RestController
@RequestMapping("/api/knowledge")
public class KnowledgeController {

	private final KnowledgeService knowledgeService;

	public KnowledgeController(KnowledgeService knowledgeService) {
		this.knowledgeService = knowledgeService;
	}

	@GetMapping("/search")
	List<KnowledgeHit> search(
		@RequestParam(defaultValue = "") String query,
		@RequestParam(defaultValue = "3") int topK
	) {
		return knowledgeService.search(query, topK);
	}
}
