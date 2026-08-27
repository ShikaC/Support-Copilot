import { useEffect, useState } from 'react'
import { ChevronDown, ChevronRight, FileSearch } from 'lucide-react'
import type { AnalysisResult } from '../../types'

export function EvidencePanel({ analysis }: { readonly analysis: AnalysisResult }) {
  const [expandedId, setExpandedId] = useState<string | null>(analysis.retrieval.hits[0]?.chunkId ?? null)
  useEffect(() => { setExpandedId(analysis.retrieval.hits[0]?.chunkId ?? null) }, [analysis.id, analysis.retrieval.hits])
  return <div className="analysis-content">
    <div className="retrieval-query"><span className="retrieval-query-label">检索查询</span><span className="retrieval-query-value">{analysis.retrieval.query}</span></div>
    {analysis.retrieval.hits.length === 0 ? <div className="no-evidence"><FileSearch size={20} /><strong>没有找到充分证据</strong><span>系统已停止自动下结论，并转入人工复核。</span></div> :
      <div className="evidence-list">{analysis.retrieval.hits.map((hit) => {
        const expanded = hit.chunkId === expandedId
        return <article className="evidence-item" key={hit.chunkId}>
          <button className="evidence-button" type="button" aria-expanded={expanded} onClick={() => setExpandedId(expanded ? null : hit.chunkId)}>
            <span className="evidence-rank">{hit.rerankPosition}</span><span><span className="evidence-title">{hit.documentTitle}</span><span className="evidence-section">{hit.section}</span></span><span className="evidence-score">{(hit.rerankScore * 100).toFixed(1)}</span>{expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
          </button>
          <div className={`evidence-expanded ${expanded ? 'open' : ''}`}><div className="evidence-expanded-inner"><p className="evidence-copy">{hit.content}</p><div className="evidence-meta"><span>{hit.retrievalMethod}</span><span>{hit.usedAsEvidence ? '已作为证据' : '未进入上下文'}</span></div></div></div>
        </article>
      })}</div>}
  </div>
}
