package com.cyagent.supportcopilot.knowledge;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.file.Files;
import java.nio.file.Path;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import tools.jackson.databind.json.JsonMapper;

class KnowledgeCorpusStoreTests {

	private static final Path CANONICAL_CORPUS = Path.of(
		"../support-copilot-ai/app/data/knowledge.json"
	);

	@TempDir
	Path tempDir;

	@Test
	void loadsTheSameReleaseAndChunkIdsUsedByPython() {
		var store = new KnowledgeCorpusStore(new JsonMapper(), CANONICAL_CORPUS);

		var corpus = store.load();

		assertThat(corpus.releaseId()).isEqualTo("support-copilot-bundled-v1");
		assertThat(corpus.releaseVersion()).isEqualTo(1);
		assertThat(corpus.corpusChecksum())
			.isEqualTo("b25240587df1ebb903a8555284a0f35faaa35e2d837add0fc5dd49418ca8b874");
		assertThat(corpus.chunks())
			.extracting(KnowledgeCorpusStore.KnowledgeChunk::chunkId)
			.containsExactly(
				"chunk-billing-07",
				"chunk-payment-04",
				"chunk-refund-02",
				"chunk-account-sso-01",
				"chunk-account-lock-02",
				"chunk-invoice-03",
				"chunk-export-04",
				"chunk-subscription-02",
				"chunk-privacy-05",
				"chunk-sync-2047"
			);
	}

	@Test
	void rejectsContentTamperingEvenWhenTheDeclaredChecksumIsUnchanged() throws Exception {
		var source = Files.readString(CANONICAL_CORPUS)
			.replace("客服不得在交易核验完成前承诺退款到账时间。", "客服不得在交易核验完成前承诺退款到账时间。篡改");
		var tamperedPath = tempDir.resolve("tampered-knowledge.json");
		Files.writeString(tamperedPath, source);

		var store = new KnowledgeCorpusStore(new JsonMapper(), tamperedPath);

		assertThatThrownBy(store::load)
			.isInstanceOf(KnowledgeAccessException.class)
			.hasMessage("Active knowledge release does not match the retrieval runtime.");
	}

	@Test
	void rejectsUnknownCorpusFieldsBeforeSearchCanUseThem() throws Exception {
		var source = Files.readString(CANONICAL_CORPUS)
			.replace("\"release_version\": 1,", "\"release_version\": 1,\n  \"untrusted_field\": true,");
		var invalidPath = tempDir.resolve("unknown-field-knowledge.json");
		Files.writeString(invalidPath, source);

		var store = new KnowledgeCorpusStore(new JsonMapper(), invalidPath);

		assertThatThrownBy(store::load).isInstanceOf(KnowledgeAccessException.class);
	}
}
