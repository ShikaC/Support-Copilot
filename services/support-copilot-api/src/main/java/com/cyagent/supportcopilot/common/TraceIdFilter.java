package com.cyagent.supportcopilot.common;

import java.io.IOException;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.slf4j.MDC;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class TraceIdFilter extends OncePerRequestFilter {

	@Override
	protected void doFilterInternal(
		HttpServletRequest request,
		HttpServletResponse response,
		FilterChain filterChain
	) throws ServletException, IOException {
		var traceId = TraceId.resolve(request.getHeader(TraceId.HEADER_NAME));
		request.setAttribute(TraceId.REQUEST_ATTRIBUTE, traceId);
		response.setHeader(TraceId.HEADER_NAME, traceId);

		try (var ignored = MDC.putCloseable(TraceId.MDC_KEY, traceId)) {
			filterChain.doFilter(request, response);
		}
	}
}
