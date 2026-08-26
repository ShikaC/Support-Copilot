package com.cyagent.supportcopilot.knowledge;

import com.cyagent.supportcopilot.analysis.AiServiceContractException;

public class KnowledgeAccessException extends AiServiceContractException {

	private final String code;

	private KnowledgeAccessException(String code, String message) {
		super(message);
		this.code = code;
	}

	public static KnowledgeAccessException inactive() {
		return new KnowledgeAccessException(
			"KNOWLEDGE_RELEASE_INACTIVE",
			"No valid published knowledge release is active."
		);
	}

	public static KnowledgeAccessException mismatch() {
		return new KnowledgeAccessException(
			"KNOWLEDGE_RELEASE_MISMATCH",
			"Active knowledge release does not match the retrieval runtime."
		);
	}

	public String code() {
		return code;
	}
}
