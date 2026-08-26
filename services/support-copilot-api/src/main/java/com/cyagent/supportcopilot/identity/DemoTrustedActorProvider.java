package com.cyagent.supportcopilot.identity;

import java.util.List;

import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

import com.cyagent.supportcopilot.identity.TrustedActorProvider.TrustedActorType;
import com.cyagent.supportcopilot.identity.TrustedActorProvider.TrustedRole;

@Component
@Profile("demo")
public class DemoTrustedActorProvider implements TrustedActorProvider {

	private static final TrustedActor ANONYMOUS_DEMO_ACTOR = new TrustedActor(
		"anonymous-demo",
		TrustedActorType.UNAUTHENTICATED_DEMO,
		List.of(TrustedRole.DEMO),
		"匿名演示操作人"
	);

	@Override
	public TrustedActor currentActor() {
		return ANONYMOUS_DEMO_ACTOR;
	}
}
