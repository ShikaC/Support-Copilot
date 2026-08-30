package com.cyagent.supportcopilot.knowledge;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDate;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.regex.Pattern;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.PropertyNamingStrategies;

/** Reads the canonical corpus shared with the Python retrieval service. */
@Component
public class KnowledgeCorpusStore {

	private static final Pattern CHECKSUM_PATTERN = Pattern.compile("[a-f0-9]{64}");

	private final ObjectMapper objectMapper;
	private final ObjectMapper corpusMapper;
	private final Path corpusPath;

	@Autowired
	public KnowledgeCorpusStore(
		ObjectMapper objectMapper,
		@Value("${support-copilot.knowledge.corpus-path}") String corpusPath
	) {
		this(objectMapper, Path.of(corpusPath));
	}

	KnowledgeCorpusStore(ObjectMapper objectMapper, Path corpusPath) {
		this.objectMapper = objectMapper;
		this.corpusMapper = objectMapper.rebuild()
			.propertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
			.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, true)
			.build();
		this.corpusPath = corpusPath.toAbsolutePath().normalize();
	}

	public KnowledgeCorpus load() {
		try {
			if (!Files.isRegularFile(corpusPath)) {
				throw new IllegalArgumentException("Knowledge corpus file is unavailable.");
			}
			var corpus = corpusMapper.readValue(corpusPath, KnowledgeCorpus.class);
			validate(corpus);
			var published = corpus.chunks().stream()
				.filter(chunk -> chunk.status().equals("PUBLISHED"))
				.toList();
			if (published.isEmpty()) {
				throw new IllegalArgumentException("Knowledge corpus has no published chunks.");
			}
			return new KnowledgeCorpus(
				corpus.releaseId(),
				corpus.releaseVersion(),
				corpus.corpusChecksum(),
				published
			);
		} catch (RuntimeException exception) {
			if (exception instanceof KnowledgeAccessException accessException) {
				throw accessException;
			}
			throw KnowledgeAccessException.mismatch();
		}
	}

	private void validate(KnowledgeCorpus corpus) {
		if (corpus == null || isBlank(corpus.releaseId()) || corpus.releaseVersion() <= 0
			|| !matchesChecksum(corpus.corpusChecksum()) || corpus.chunks().isEmpty()) {
			throw new IllegalArgumentException("Knowledge corpus metadata is invalid.");
		}

		var chunkIds = new HashSet<String>();
		for (var chunk : corpus.chunks()) {
			if (!chunkIds.add(chunk.chunkId()) || isBlank(chunk.chunkId())
				|| isBlank(chunk.documentId()) || isBlank(chunk.documentTitle())
				|| isBlank(chunk.section()) || isBlank(chunk.content())
				|| isBlank(chunk.sourceUri()) || isBlank(chunk.documentVersion())
				|| chunk.categories().isEmpty() || chunk.keywords().isEmpty()
				|| chunk.allowedScopes().isEmpty() || !isValidStatus(chunk.status())) {
				throw new IllegalArgumentException("Knowledge chunk is invalid.");
			}
			validateTexts(chunk.categories());
			validateTexts(chunk.keywords());
			KnowledgeScope.canonicalize(chunk.allowedScopes());
			try {
				LocalDate.parse(chunk.updatedAt());
			} catch (RuntimeException exception) {
				throw new IllegalArgumentException("Knowledge chunk date is invalid.", exception);
			}
		}

		if (!calculateChecksum(corpus.chunks()).equals(corpus.corpusChecksum())) {
			throw new IllegalArgumentException("Knowledge corpus checksum does not match its chunks.");
		}
	}

	private void validateTexts(List<String> values) {
		if (values.stream().anyMatch(KnowledgeCorpusStore::isBlank)) {
			throw new IllegalArgumentException("Knowledge chunk contains a blank value.");
		}
	}

	private String calculateChecksum(List<KnowledgeChunk> chunks) {
		var canonicalChunks = chunks.stream().map(this::canonicalChunk).toList();
		var canonicalJson = objectMapper.writeValueAsBytes(canonicalChunks);
		try {
			return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(canonicalJson));
		} catch (NoSuchAlgorithmException exception) {
			throw new IllegalStateException("SHA-256 is unavailable.", exception);
		}
	}

	private Map<String, Object> canonicalChunk(KnowledgeChunk chunk) {
		var canonical = new TreeMap<String, Object>();
		canonical.put("allowed_scopes", chunk.allowedScopes());
		canonical.put("categories", chunk.categories());
		canonical.put("chunk_id", chunk.chunkId());
		canonical.put("content", chunk.content());
		canonical.put("document_id", chunk.documentId());
		canonical.put("document_title", chunk.documentTitle());
		canonical.put("document_version", chunk.documentVersion());
		canonical.put("keywords", chunk.keywords());
		canonical.put("section", chunk.section());
		canonical.put("source_uri", chunk.sourceUri());
		canonical.put("status", chunk.status());
		canonical.put("updated_at", chunk.updatedAt());
		return canonical;
	}

	private static boolean isValidStatus(String status) {
		return "PUBLISHED".equals(status) || "ARCHIVED".equals(status);
	}

	private static boolean matchesChecksum(String checksum) {
		return checksum != null && CHECKSUM_PATTERN.matcher(checksum).matches();
	}

	private static boolean isBlank(String value) {
		return value == null || value.isBlank();
	}

	public record KnowledgeCorpus(
		String releaseId,
		int releaseVersion,
		String corpusChecksum,
		List<KnowledgeChunk> chunks
	) {
		public KnowledgeCorpus {
			chunks = List.copyOf(chunks);
		}
	}

	public record KnowledgeChunk(
		String chunkId,
		String documentId,
		String documentTitle,
		String section,
		String content,
		String sourceUri,
		List<String> categories,
		List<String> keywords,
		List<String> allowedScopes,
		String documentVersion,
		String status,
		String updatedAt
	) {
		public KnowledgeChunk {
			categories = List.copyOf(categories);
			keywords = List.copyOf(keywords);
			allowedScopes = List.copyOf(allowedScopes);
		}
	}
}
