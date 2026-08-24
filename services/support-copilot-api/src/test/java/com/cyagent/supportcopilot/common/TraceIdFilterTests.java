package com.cyagent.supportcopilot.common;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import java.io.IOException;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;

import org.junit.jupiter.api.Test;
import org.slf4j.MDC;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

class TraceIdFilterTests {

	private final TraceIdFilter filter = new TraceIdFilter();

	@Test
	void preservesIncomingTraceIdAcrossResponseAndMdc() throws ServletException, IOException {
		var request = new MockHttpServletRequest("GET", "/api/tickets");
		request.addHeader(TraceId.HEADER_NAME, "trace-test");
		var response = new MockHttpServletResponse();
		var chain = mock(FilterChain.class);
		doAnswer(invocation -> {
			assertThat(MDC.get(TraceId.MDC_KEY)).isEqualTo("trace-test");
			return null;
		}).when(chain).doFilter(request, response);

		filter.doFilter(request, response, chain);

		assertThat(response.getHeader(TraceId.HEADER_NAME)).isEqualTo("trace-test");
		verify(chain).doFilter(request, response);
		assertThat(MDC.get(TraceId.MDC_KEY)).isNull();
	}

	@Test
	void generatesTraceIdWhenRequestDoesNotProvideOne() throws ServletException, IOException {
		var request = new MockHttpServletRequest("GET", "/api/tickets");
		var response = new MockHttpServletResponse();
		var chain = mock(FilterChain.class);
		doAnswer(invocation -> {
			assertThat(MDC.get(TraceId.MDC_KEY)).isEqualTo(response.getHeader(TraceId.HEADER_NAME));
			return null;
		}).when(chain).doFilter(request, response);

		filter.doFilter(request, response, chain);

		assertThat(response.getHeader(TraceId.HEADER_NAME)).matches("trace_[A-Za-z0-9]{12}");
		verify(chain).doFilter(request, response);
	}
}
