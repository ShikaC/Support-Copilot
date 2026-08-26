package com.cyagent.supportcopilot.knowledge;

import java.util.Arrays;
import java.util.List;

import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

@Component
@Profile("demo")
public class DemoTrustedSupportScopeProvider implements TrustedSupportScopeProvider {
	@Override
	public List<KnowledgeScope> currentScopes() {
		return Arrays.asList(KnowledgeScope.values());
	}
}
