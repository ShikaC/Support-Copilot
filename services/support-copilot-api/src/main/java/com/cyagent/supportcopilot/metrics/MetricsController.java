package com.cyagent.supportcopilot.metrics;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.cyagent.supportcopilot.metrics.MetricsService.MetricsResponse;

@RestController
@RequestMapping("/api/metrics")
public class MetricsController {

	private final MetricsService metricsService;

	public MetricsController(MetricsService metricsService) {
		this.metricsService = metricsService;
	}

	@GetMapping
	MetricsResponse metrics() {
		return metricsService.snapshot();
	}
}
