from __future__ import annotations

import logging

from ..core.models import Document

logger = logging.getLogger(__name__)

_MAX_DOCS = 3
_MAX_CHARS = 500


class KnowledgeRetriever:
    """
    LlamaIndex 기반 지식 검색기.
    실패 시 빈 리스트 반환 (전체 파이프라인 중단 없음).
    """

    def retrieve(self, query: str, top_k: int = 5) -> list[Document]:
        try:
            return self._retrieve_web(query, min(top_k, _MAX_DOCS))
        except Exception as e:
            logger.warning("KnowledgeRetriever failed: %s", e)
            return []

    def _retrieve_web(self, query: str, top_k: int) -> list[Document]:
        try:
            from llama_index.readers.web import SimpleWebPageReader  # type: ignore
        except ImportError:
            logger.warning("llama-index-readers-web not available, skipping retrieval")
            return []

        # 실제 환경에서는 검색 결과 URL을 동적으로 가져와야 함
        # 여기서는 구조만 정의하고, 실제 URL 없이는 빈 리스트 반환
        return []

    def retrieve_from_texts(self, texts: list[str], source: str = "user_upload") -> list[Document]:
        """사용자 제공 텍스트를 Document로 변환."""
        docs = []
        for text in texts[:_MAX_DOCS]:
            docs.append(Document(
                content=text[:_MAX_CHARS],
                source=source,
                relevance=1.0,
            ))
        return docs
