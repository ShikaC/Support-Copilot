export function analysisResponsePayload(id: string) {
  return {
    id,
    traceId: 'trace-contract-test',
    status: 'SUCCEEDED',
    mode: 'mock',
    fallbackReason: null,
    modelName: 'mock-rules-v1',
    promptVersion: 'ticket-analysis-v1',
    classification: {
      intent: 'duplicate_charge',
      category: 'BILLING',
      priority: 'HIGH',
      sentiment: 'NEGATIVE',
      confidence: 0.91,
      reasonSummary: '账单重复扣款需要人工核验。',
    },
    workflowSteps: [
      {
        id: 'retrieve',
        name: '知识检索',
        description: '命中退款政策。',
        status: 'complete',
        durationMs: 12,
      },
    ],
    retrieval: {
      query: '重复扣款',
      hits: [
        {
          chunkId: 'chunk-billing-01',
          documentId: 'kb-billing',
          documentTitle: '账单政策',
          section: '重复扣款',
          content: '核验完成前不得承诺退款。',
          sourceUri: 'kb://billing#duplicate-charge',
          retrievalMethod: 'KEYWORD',
          initialRank: 1,
          initialScore: 1,
          rerankPosition: 1,
          rerankScore: 1,
          usedAsEvidence: true,
        },
      ],
    },
    suggestedReply: {
      content: '我们会先核验交易记录。[1]',
      citations: ['账单政策：重复扣款'],
      warnings: ['核验前不得承诺退款。'],
    },
    decision: {
      escalationRequired: true,
      reason: '支付争议需要人工复核。',
    },
    usage: {
      inputTokens: 0,
      outputTokens: 0,
      durationMs: 25,
    },
    createdAt: '2026-08-25T02:00:00Z',
  }
}

export const ticketResponsePayload = {
  id: 'ticket-10042',
  ticketNo: 'SC-10042',
  channel: 'EMAIL',
  customerName: '测试客户',
  customerCompany: '测试企业',
  customerTier: 'ENTERPRISE',
  subject: '本月套餐出现重复扣款',
  description: '同一笔订单出现两次扣款。',
  language: 'zh-CN',
  category: 'BILLING',
  priority: 'HIGH',
  status: 'NEW',
  assigneeName: null,
  slaDeadline: '2026-08-26T02:00:00Z',
  createdAt: '2026-08-25T01:00:00Z',
  updatedAt: '2026-08-25T01:30:00Z',
  version: 0,
  latestAnalysis: null,
  latestReview: null,
  events: [],
} as const

export function analysisReviewPayload(id: string) {
  return {
    id,
    ticketId: 'ticket-10042',
    analysisId: 'analysis-1',
    action: 'EDITED',
    reviewerType: 'UNAUTHENTICATED_DEMO',
    reviewerLabel: '演示管理员',
    originalReplyContent: '我们会先核验交易记录。[1]',
    reviewedReplyContent: '我们会先核验交易记录，并同步处理进展。[1]',
    reason: null,
    ticketVersion: 4,
    traceId: 'trace-contract-test',
    createdAt: '2026-08-25T08:00:00Z',
  }
}

export const metricsResponsePayload = {
  summary: {
    openTickets: 6,
    urgentTickets: 1,
    slaRiskTickets: 2,
    analysisSuccessRate: 0.94,
  },
  ticketTrend: [{ date: '08-25', created: 6, resolved: 4 }],
  categoryDistribution: [{ category: '账单支付', count: 2 }],
  analysisLatency: {
    averageMs: 120,
    p95Ms: 280,
  },
  suggestionAcceptanceRate: 0.71,
  evaluation: {
    datasetName: 'tickets.jsonl',
    mode: 'mock',
    modelName: 'deterministic-demo',
    promptVersion: 'ticket-analysis-v1',
    totalCases: 31,
    topN: 10,
    topK: 3,
    hitRateAtK: 0.88,
    mrr: 0.82,
    citationCoverage: 0.95,
    noEvidenceSafetyRate: 1,
    averageDurationMs: 2.42,
    p95DurationMs: 14,
    thresholdFailureCount: 0,
    passed: true,
    generatedAt: '2026-08-26T06:53:34.585167Z',
  },
} as const

export const nullableMetricsResponsePayload = {
  ...metricsResponsePayload,
  summary: {
    ...metricsResponsePayload.summary,
    analysisSuccessRate: null,
  },
  analysisLatency: null,
  suggestionAcceptanceRate: null,
  evaluation: null,
} as const

export const knowledgeHitPayload = {
  chunkId: 'chunk-policy-1',
  documentTitle: '账单核验政策',
  section: '重复扣款',
  content: '<img src=x onerror=alert(1)> 请先核验交易记录。',
  documentType: 'POLICY',
  score: 0.94,
}

export const knowledgeReleasePayload = {
  releaseId: 'release-2026-08',
  releaseVersion: 3,
  corpusChecksum: 'a'.repeat(64),
  allowedScopes: ['BILLING'],
  status: 'DRAFT',
  createdBy: 'knowledge-admin',
  createdAt: '2026-08-27T01:00:00Z',
  approvedBy: null,
  approvedAt: null,
  publishedBy: null,
  publishedAt: null,
  version: 2,
}

export const auditEventPayload = {
  id: 'audit-1',
  actorSubject: 'reviewer-42',
  actorType: 'USER',
  actorRoles: ['REVIEWER'],
  action: 'ANALYSIS_REVIEW_APPROVED',
  targetType: 'ANALYSIS_REVIEW',
  targetId: 'review-1',
  targetVersion: 4,
  traceId: 'trace-audit-1',
  createdAt: '2026-08-27T02:00:00Z',
  metadata: {
    reviewAction: 'APPROVED',
    sourceVersion: 4,
    resultId: 'analysis-1',
  },
}
