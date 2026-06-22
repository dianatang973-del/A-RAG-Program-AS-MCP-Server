import sys
sys.path.insert(0, 'C:/Users/tangz/Documents/trae_projects/project1/MODULAR-RAG-MCP-SERVER')

from src.core.settings import load_settings
from src.libs.reranker.reranker_factory import RerankerFactory

settings = load_settings()
print(f'Rerank enabled: {settings.rerank.enabled}')
print(f'Rerank provider: {settings.rerank.provider}')
print(f'Rerank model: {settings.rerank.model}')
print(f'Rerank base_url: {settings.rerank.base_url}')
print(f'Rerank api_key: {settings.rerank.api_key[:10]}...' if settings.rerank.api_key else 'None')

reranker = RerankerFactory.create(settings)
print(f'Reranker created: {type(reranker).__name__}')
print(f'Use rerank API: {getattr(reranker, "_use_rerank_api", False)}')
print(f'API URL: {getattr(reranker, "rerank_base_url", None)}')

# Test rerank
try:
    result = reranker.rerank('test query', [
        {'id': '1', 'text': 'This is a test document about Python programming.', 'score': 0.5},
        {'id': '2', 'text': 'Machine learning is a subset of artificial intelligence.', 'score': 0.4}
    ])
    print(f'Rerank result: {len(result)} items')
    for r in result:
        print(f'  - id={r["id"]}, rerank_score={r.get("rerank_score", "N/A")}')
except Exception as e:
    print(f'Rerank failed: {e}')
    import traceback
    traceback.print_exc()
