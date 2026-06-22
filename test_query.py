import sys
sys.path.insert(0, 'C:/Users/tangz/Documents/trae_projects/project1/MODULAR-RAG-MCP-SERVER')

from src.core.settings import load_settings
from src.core.query_engine.query_processor import QueryProcessor
from src.core.query_engine.hybrid_search import create_hybrid_search
from src.core.query_engine.dense_retriever import create_dense_retriever
from src.core.query_engine.sparse_retriever import create_sparse_retriever
from src.core.query_engine.reranker import create_core_reranker
from src.core.trace import TraceContext, TraceCollector
from src.ingestion.storage.bm25_indexer import BM25Indexer
from src.libs.embedding.embedding_factory import EmbeddingFactory
from src.libs.vector_store.vector_store_factory import VectorStoreFactory

settings = load_settings()
collection = 'test'

print('=' * 60)
print('Testing Query with Rerank')
print('=' * 60)

# Build components
vector_store = VectorStoreFactory.create(settings, collection_name=collection)
embedding_client = EmbeddingFactory.create(settings)
dense_retriever = create_dense_retriever(settings=settings, embedding_client=embedding_client, vector_store=vector_store)
bm25_indexer = BM25Indexer(index_dir=f"data/db/bm25/{collection}")
sparse_retriever = create_sparse_retriever(settings=settings, bm25_indexer=bm25_indexer, vector_store=vector_store)
sparse_retriever.default_collection = collection

query_processor = QueryProcessor()
hybrid_search = create_hybrid_search(settings=settings, query_processor=query_processor, dense_retriever=dense_retriever, sparse_retriever=sparse_retriever)

reranker = create_core_reranker(settings=settings)
print(f'Reranker enabled: {reranker.is_enabled}')
print(f'Reranker type: {reranker.reranker_type}')

# Run query
query = "测试查询"
trace = TraceContext(trace_type="query")
trace.metadata["query"] = query

print(f'\nQuery: {query}')
print('-' * 60)

hybrid_result = hybrid_search.search(query=query, top_k=10, filters=None, trace=trace, return_details=True)
results = hybrid_result.results

print(f'Fusion results: {len(results)} items')

# Rerank
if reranker.is_enabled:
    print('\nRunning rerank...')
    rerank_result = reranker.rerank(query=query, results=results, top_k=5, trace=trace)
    results = rerank_result.results
    print(f'Rerank used fallback: {rerank_result.used_fallback}')
    print(f'Rerank results: {len(results)} items')
    
    for i, r in enumerate(results):
        print(f'  #{i+1} score={r.score:.4f} rerank_score={r.metadata.get("rerank_score", "N/A")} id={r.chunk_id[:20]}...')

TraceCollector().collect(trace)
print('\nDone!')
