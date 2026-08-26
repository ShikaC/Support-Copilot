package com.cyagent.supportcopilot.knowledge;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.cyagent.supportcopilot.knowledge.KnowledgeReleaseDtos.CreateReleaseRequest;
import com.cyagent.supportcopilot.knowledge.KnowledgeReleaseDtos.ReleaseResponse;
import com.cyagent.supportcopilot.knowledge.KnowledgeReleaseDtos.TransitionRequest;

@RestController
@RequestMapping("/api/knowledge/releases")
public class KnowledgeReleaseController {

	private final KnowledgeReleaseService service;

	public KnowledgeReleaseController(KnowledgeReleaseService service) {
		this.service = service;
	}

	@GetMapping
	List<ReleaseResponse> list() {
		return service.list();
	}

	@GetMapping("/active")
	ReleaseResponse active() {
		return service.active();
	}

	@GetMapping("/{releaseId}")
	ReleaseResponse get(@PathVariable String releaseId) {
		return service.get(releaseId);
	}

	@PostMapping
	@ResponseStatus(HttpStatus.CREATED)
	ReleaseResponse create(@RequestBody CreateReleaseRequest request) {
		return service.create(request);
	}

	@PostMapping("/{releaseId}/approve")
	ReleaseResponse approve(@PathVariable String releaseId, @RequestBody TransitionRequest request) {
		return service.approve(releaseId, request.expectedVersion());
	}

	@PostMapping("/{releaseId}/publish")
	ReleaseResponse publish(@PathVariable String releaseId, @RequestBody TransitionRequest request) {
		return service.publish(releaseId, request.expectedVersion());
	}

	@PostMapping("/{releaseId}/rollback")
	ReleaseResponse rollback(@PathVariable String releaseId, @RequestBody TransitionRequest request) {
		return service.rollback(releaseId, request.expectedVersion());
	}
}
