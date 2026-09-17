package com.cyagent.supportcopilot.quality;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class QualityReportsController {
	private final QualityReportsReader reader;

	public QualityReportsController(QualityReportsReader reader) {
		this.reader = reader;
	}

	@GetMapping("/api/quality-reports")
	public QualityReportsReader.Reports reports() {
		return reader.read();
	}
}
