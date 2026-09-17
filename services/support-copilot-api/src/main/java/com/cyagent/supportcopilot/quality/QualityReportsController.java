package com.cyagent.supportcopilot.quality;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/quality-reports")
public class QualityReportsController {
	private final QualityReportsReader reader;

	public QualityReportsController(QualityReportsReader reader) {
		this.reader = reader;
	}

	@GetMapping
	public QualityReportsReader.Reports reports() {
		return reader.read();
	}
}
