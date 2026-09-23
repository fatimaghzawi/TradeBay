"""Shared AI provider layer.

Domain modules call `get_ai_provider()` for advisory extraction only.
Marketplace truth stays in catalog / identity / procurement collections.

Optional RAG (`get_rag_retriever`) supplies catalog vocabulary context —
never prices, stock, or verification.
"""

from app.modules.ai.provider import AIProvider, AIProviderError, get_ai_provider
from app.modules.ai.rag import (
    RagChunk,
    RagRetriever,
    ensure_catalog_rag_index,
    format_rag_context,
    get_rag_retriever,
    reset_rag_cache,
)

__all__ = [
    "AIProvider",
    "AIProviderError",
    "RagChunk",
    "RagRetriever",
    "ensure_catalog_rag_index",
    "format_rag_context",
    "get_ai_provider",
    "get_rag_retriever",
    "reset_rag_cache",
]
