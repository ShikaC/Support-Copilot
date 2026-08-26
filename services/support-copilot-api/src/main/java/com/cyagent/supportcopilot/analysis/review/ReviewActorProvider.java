package com.cyagent.supportcopilot.analysis.review;

public interface ReviewActorProvider {

	ReviewActor currentActor();

	record ReviewActor(String type, String label) {
	}
}
