# /// script
# requires-python = ">=3.11"
# dependencies = ["langchain-openai", "numpy", "anyio", "pydantic-settings"]
# ///
# Run: PYTHONPATH=. .venv/bin/python /tmp/support-embedding-ab.py
import json
from pathlib import Path
from datetime import datetime, timezone
import anyio
import numpy as np
from langchain_openai import OpenAIEmbeddings
from app.config import Settings
from app.knowledge_source import load_knowledge_corpus
from app.data_redaction import redact_sensitive_text

async def main() -> None:
    settings = Settings()
    corpus = load_knowledge_corpus(settings.knowledge_path)
    texts = [redact_sensitive_text(c.content) for c in corpus.chunks]
    queries = ["企业 SSO 登录循环，Azure AD 域名配置没有改动，如何排查？", "发票抬头填错了，需要更正发票信息。", "导出数据任务一直失败，文件无法下载。"]
    results = []
    for tokenized in [True, False]:
        client = OpenAIEmbeddings(api_key=settings.embedding_api_key, base_url=settings.embedding_base_url, model=settings.openai_embedding_model, max_retries=0, request_timeout=30, check_embedding_ctx_length=tokenized)
        matrix = np.asarray(await client.aembed_documents(texts))
        rows = []
        for query in queries:
            vector = np.asarray(await client.aembed_query(query))
            scores = matrix @ vector / (np.linalg.norm(matrix, axis=1) * np.linalg.norm(vector))
            order = np.argsort(-scores)[:3]
            rows.append({"query": query, "top3": [{"chunk_id": corpus.chunks[int(i)].chunk_id, "score": round(float(scores[i]), 6)} for i in order]})
        results.append({"input_format": "cl100k-token-ids" if tokenized else "raw-text-v1", "dimension": matrix.shape[1], "results": rows})
    output = {"timestamp": datetime.now(timezone.utc).isoformat(), "model": settings.openai_embedding_model, "corpus_checksum": corpus.corpus_checksum, "document_count": len(texts), "embedding_calls": 8, "chat_calls": 0, "comparisons": results}
    Path('/tmp/support-embedding-ab.json').write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(json.dumps(output, ensure_ascii=False, indent=2))
anyio.run(main)
