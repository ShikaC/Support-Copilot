package com.cyagent.supportcopilot.knowledge;

import java.time.Instant;
import java.util.List;

import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import tools.jackson.core.JacksonException;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;

import com.cyagent.supportcopilot.audit.AuditAction;
import com.cyagent.supportcopilot.audit.AuditEventCommand;
import com.cyagent.supportcopilot.audit.AuditEventRecorder;
import com.cyagent.supportcopilot.audit.AuditMetadata;
import com.cyagent.supportcopilot.audit.AuditTargetType;
import com.cyagent.supportcopilot.identity.TrustedActorProvider;
import com.cyagent.supportcopilot.knowledge.KnowledgeReleaseDtos.CreateReleaseRequest;
import com.cyagent.supportcopilot.knowledge.KnowledgeReleaseDtos.ReleaseResponse;

@Service
public class KnowledgeReleaseService {

	private final KnowledgeReleaseRepository releaseRepository;
	private final KnowledgeActiveReleaseRepository activeRepository;
	private final TrustedActorProvider actorProvider;
	private final AuditEventRecorder auditEventRecorder;
	private final ObjectMapper objectMapper;

	public KnowledgeReleaseService(
		KnowledgeReleaseRepository releaseRepository,
		KnowledgeActiveReleaseRepository activeRepository,
		TrustedActorProvider actorProvider,
		AuditEventRecorder auditEventRecorder,
		ObjectMapper objectMapper
	) {
		this.releaseRepository = releaseRepository;
		this.activeRepository = activeRepository;
		this.actorProvider = actorProvider;
		this.auditEventRecorder = auditEventRecorder;
		this.objectMapper = objectMapper;
	}

	@Transactional(readOnly = true)
	public List<ReleaseResponse> list() {
		return releaseRepository.findAllByOrderByReleaseVersionDesc().stream().map(this::response).toList();
	}

	@Transactional(readOnly = true)
	public ReleaseResponse get(String releaseId) {
		return response(find(releaseId));
	}

	@Transactional(readOnly = true)
	public ReleaseResponse active() {
		var pointer = activeRepository.findById(KnowledgeActiveRelease.SINGLETON_ID)
			.orElseThrow(KnowledgeAccessException::inactive);
		return response(find(pointer.getReleaseId()));
	}

	@Transactional
	public ReleaseResponse create(CreateReleaseRequest request) {
		validateIdentity(request);
		var scopes = KnowledgeScope.canonicalize(request.allowedScopes());
		var actor = actorProvider.currentActor().subject();
		var release = new KnowledgeRelease(
			request.releaseId(),
			request.releaseVersion(),
			request.corpusChecksum(),
			serializeScopes(scopes),
			actor,
			Instant.now()
		);
		try {
			releaseRepository.saveAndFlush(release);
		} catch (DataIntegrityViolationException exception) {
			throw new IllegalArgumentException("Knowledge release id or version already exists.", exception);
		}
		record(AuditAction.KNOWLEDGE_RELEASE_DRAFT_CREATED, release, scopes);
		return response(release);
	}

	@Transactional
	public ReleaseResponse approve(String releaseId, long expectedVersion) {
		var release = checked(releaseId, expectedVersion);
		if (release.getStatus() != KnowledgeReleaseStatus.DRAFT) {
			throw KnowledgeReleaseException.illegalTransition(releaseId);
		}
		release.approve(actorProvider.currentActor().subject(), Instant.now());
		releaseRepository.flush();
		record(AuditAction.KNOWLEDGE_RELEASE_APPROVED, release, scopes(release));
		return response(release);
	}

	@Transactional
	public ReleaseResponse publish(String releaseId, long expectedVersion) {
		var release = checked(releaseId, expectedVersion);
		if (release.getStatus() != KnowledgeReleaseStatus.APPROVED) {
			throw KnowledgeReleaseException.illegalTransition(releaseId);
		}
		var actor = actorProvider.currentActor().subject();
		var pointer = activeRepository.findForUpdate().orElse(null);
		if (pointer != null && !pointer.getReleaseId().equals(releaseId)) {
			var current = find(pointer.getReleaseId());
			current.archive();
			pointer.activate(releaseId);
		} else if (pointer == null) {
			activeRepository.save(new KnowledgeActiveRelease(releaseId));
		}
		release.publish(actor, Instant.now());
		releaseRepository.flush();
		record(AuditAction.KNOWLEDGE_RELEASE_PUBLISHED, release, scopes(release));
		return response(release);
	}

	@Transactional
	public ReleaseResponse rollback(String releaseId, long expectedVersion) {
		var release = checked(releaseId, expectedVersion);
		if (release.getStatus() != KnowledgeReleaseStatus.ARCHIVED) {
			throw KnowledgeReleaseException.illegalTransition(releaseId);
		}
		var pointer = activeRepository.findForUpdate().orElseThrow(KnowledgeAccessException::inactive);
		var current = find(pointer.getReleaseId());
		if (current.getStatus() != KnowledgeReleaseStatus.PUBLISHED) {
			throw KnowledgeAccessException.inactive();
		}
		var actor = actorProvider.currentActor().subject();
		current.archive();
		release.publish(actor, Instant.now());
		pointer.activate(releaseId);
		releaseRepository.flush();
		record(AuditAction.KNOWLEDGE_RELEASE_ROLLED_BACK, release, scopes(release));
		return response(release);
	}

	private KnowledgeRelease checked(String releaseId, long expectedVersion) {
		var release = find(releaseId);
		if (release.getVersion() != expectedVersion) {
			throw KnowledgeReleaseException.stale(releaseId);
		}
		return release;
	}

	private KnowledgeRelease find(String releaseId) {
		return releaseRepository.findById(releaseId)
			.orElseThrow(() -> KnowledgeReleaseException.notFound(releaseId));
	}

	private void validateIdentity(CreateReleaseRequest request) {
		if (request.releaseId() == null || request.releaseId().isBlank()
			|| !request.releaseId().matches("[A-Za-z0-9][A-Za-z0-9._:-]{0,63}")
			|| request.releaseVersion() <= 0) {
			throw new IllegalArgumentException("Knowledge release identity is invalid.");
		}
		if (request.corpusChecksum() == null || !request.corpusChecksum().matches("[a-f0-9]{64}")) {
			throw KnowledgeReleaseException.invalidChecksum();
		}
	}

	private void record(AuditAction action, KnowledgeRelease release, List<KnowledgeScope> scopes) {
		auditEventRecorder.record(new AuditEventCommand(
			action,
			AuditTargetType.KNOWLEDGE_RELEASE,
			release.getReleaseId(),
			release.getVersion(),
			new AuditMetadata.KnowledgeRelease(
				release.getReleaseId(),
				release.getReleaseVersion(),
				release.getCorpusChecksum(),
				KnowledgeScope.names(scopes),
				release.getStatus().name()
			)
		));
	}

	private ReleaseResponse response(KnowledgeRelease release) {
		return new ReleaseResponse(
			release.getReleaseId(),
			release.getReleaseVersion(),
			release.getCorpusChecksum(),
			KnowledgeScope.names(scopes(release)),
			release.getStatus(),
			release.getCreatedBy(),
			release.getCreatedAt(),
			release.getApprovedBy(),
			release.getApprovedAt(),
			release.getPublishedBy(),
			release.getPublishedAt(),
			release.getVersion()
		);
	}

	private String serializeScopes(List<KnowledgeScope> scopes) {
		try {
			return objectMapper.writeValueAsString(KnowledgeScope.names(scopes));
		} catch (JacksonException exception) {
			throw new IllegalStateException("Unable to serialize knowledge scopes.", exception);
		}
	}

	private List<KnowledgeScope> scopes(KnowledgeRelease release) {
		try {
			var names = objectMapper.readValue(
				release.getAllowedScopesJson(),
				new TypeReference<List<String>>() { }
			);
			return KnowledgeScope.canonicalize(names);
		} catch (JacksonException exception) {
			throw KnowledgeAccessException.mismatch();
		}
	}
}
