package com.cyagent.supportcopilot.analysis.review;

import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

import com.cyagent.supportcopilot.analysis.review.ReviewActorProvider.ReviewActor;

@Component
@Profile("demo")
public class DemoReviewActorProvider implements ReviewActorProvider {

	private static final ReviewActor ANONYMOUS_DEMO_ACTOR =
		new ReviewActor("UNAUTHENTICATED_DEMO", "匿名演示操作人");

	@Override
	public ReviewActor currentActor() {
		return ANONYMOUS_DEMO_ACTOR;
	}
}
