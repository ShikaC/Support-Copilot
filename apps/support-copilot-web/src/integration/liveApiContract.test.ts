import { expect, it } from 'vitest'

import {
  analyzeTicket,
  fetchMetrics,
  fetchTickets,
  reviewAnalysisReply,
} from '../services/api'

const CONTRACT_TEST_ENABLED = import.meta.env.VITE_CONTRACT_TEST_ENABLED === 'true'
const CONTRACT_TICKET_ID = import.meta.env.VITE_CONTRACT_TICKET_ID ?? 'ticket-10042'

it.skipIf(!CONTRACT_TEST_ENABLED)(
  'parses the real ticket list through the frontend runtime schema',
  async () => {
    // Given: the React proxy and Java API are running with demo tickets.

    // When: the production API client reads the real ticket response.
    const tickets = await fetchTickets()

    // Then: the configured contract ticket crossed the same Zod boundary used by the page.
    expect(tickets.some((ticket) => ticket.id === CONTRACT_TICKET_ID)).toBe(true)
  },
)

it.skipIf(!CONTRACT_TEST_ENABLED)(
  'parses the real metrics response through the frontend runtime schema',
  async () => {
    // Given: the React proxy and Java metrics endpoint are running.

    // When: the production API client reads the real metrics response.
    const metrics = await fetchMetrics()

    // Then: runtime parsing preserved a valid non-negative ticket count.
    expect(metrics.summary.openTickets).toBeGreaterThanOrEqual(0)
  },
)

it.skipIf(!CONTRACT_TEST_ENABLED)(
  'parses and persists a real mock analysis through the frontend runtime schema',
  async () => {
    // Given: React, Java, and Python mock services are running.

    // When: the production API client triggers one cross-service analysis.
    const analysis = await analyzeTicket(CONTRACT_TICKET_ID)

    // Then: the response is evidence-bearing mock success, and a refreshed ticket exposes it.
    expect(analysis).toMatchObject({
      mode: 'mock',
      status: 'SUCCEEDED',
      fallbackReason: null,
    })
    expect(analysis.retrieval.hits.length).toBeGreaterThan(0)
    expect(analysis.suggestedReply.citations.length).toBeGreaterThan(0)

    const review = await reviewAnalysisReply(
      CONTRACT_TICKET_ID,
      analysis.id,
      analysis.suggestedReply.content,
    )
    expect(review).toMatchObject({
      action: 'APPROVED',
      reviewerType: 'UNAUTHENTICATED_DEMO',
      analysisId: analysis.id,
    })

    const refreshedTickets = await fetchTickets()
    const refreshedTicket = refreshedTickets.find((ticket) => ticket.id === CONTRACT_TICKET_ID)
    expect(refreshedTicket?.latestAnalysis?.id).toBe(analysis.id)
    expect(refreshedTicket?.latestReview?.id).toBe(review.id)
  },
)
