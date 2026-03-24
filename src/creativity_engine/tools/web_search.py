from __future__ import annotations

import logging
import os

from ..core.models import Document, Signal

logger = logging.getLogger(__name__)

_MAX_CHARS = 500


class WebSearchTool:
    """
    Tavily 기반 웹 검색 도구.
    TAVILY_API_KEY 없으면 gracefully 빈 결과 반환.
    """

    def __init__(self) -> None:
        self._client = None
        api_key = os.environ.get("TAVILY_API_KEY")
        if api_key:
            try:
                from tavily import TavilyClient  # type: ignore
                self._client = TavilyClient(api_key=api_key)
            except ImportError:
                logger.warning("tavily-python not installed, web search disabled")

    def search(self, query: str, max_results: int = 5) -> list[Document]:
        if not self._client:
            return []
        try:
            response = self._client.search(query=query, max_results=max_results)
            results = response.get("results", [])
            return [
                Document(
                    content=(r.get("content") or r.get("snippet") or "")[:_MAX_CHARS],
                    source="web",
                    relevance=r.get("score", 0.5),
                    metadata={"url": r.get("url", ""), "title": r.get("title", "")},
                )
                for r in results
            ]
        except Exception as e:
            logger.warning("WebSearchTool.search failed: %s", e)
            return []

    def search_signals(self, query: str, max_results: int = 5) -> list[Signal]:
        """엣지케이스·트렌드 신호 수집."""
        if not self._client:
            return []
        try:
            response = self._client.search(
                query=f"{query} edge cases challenges trends",
                max_results=max_results,
            )
            results = response.get("results", [])
            signals = []
            for i, r in enumerate(results):
                content = (r.get("content") or r.get("snippet") or "")[:_MAX_CHARS]
                if not content:
                    continue
                signal_type = "trend" if i % 2 == 0 else "edge_case"
                signals.append(Signal(
                    content=content,
                    signal_type=signal_type,
                    strength=r.get("score", 0.3),
                ))
            return signals
        except Exception as e:
            logger.warning("WebSearchTool.search_signals failed: %s", e)
            return []
