package com.cyagent.supportcopilot.idempotency;

public sealed interface CommandResolution {

	record Owned(CommandOwnership ownership) implements CommandResolution {
	}

	record Replay(int httpStatus, String responseJson) implements CommandResolution {
	}

	record Pending() implements CommandResolution {
	}
}
