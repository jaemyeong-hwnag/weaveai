"""tools 단위 테스트 — 외부 I/O mock."""
import os
from unittest.mock import MagicMock, patch

import pytest

from creativity_engine.tools.retriever import KnowledgeRetriever
from creativity_engine.tools.web_search import WebSearchTool
from creativity_engine.core.models import Document, Signal


# ── KnowledgeRetriever ───────────────────────────────────

class TestKnowledgeRetriever:
    def test_retrieve_returns_empty_when_no_urls(self):
        retriever = KnowledgeRetriever()
        result = retriever.retrieve("테스트 쿼리")
        assert result == []

    def test_retrieve_handles_exception_gracefully(self):
        retriever = KnowledgeRetriever()
        with patch.object(retriever, "_retrieve_web", side_effect=Exception("오류")):
            result = retriever.retrieve("쿼리")
        assert result == []

    def test_retrieve_web_returns_empty_when_llama_available(self):
        """llama-index 설치되어 있어도 URL 없으면 빈 리스트."""
        retriever = KnowledgeRetriever()
        result = retriever._retrieve_web("쿼리", top_k=3)
        assert result == []

    def test_retrieve_web_handles_import_error(self):
        retriever = KnowledgeRetriever()
        with patch.dict("sys.modules", {"llama_index.readers.web": None}):
            # ImportError 발생 시 빈 리스트 반환
            result = retriever._retrieve_web("쿼리", top_k=3)
        assert result == []

    def test_retrieve_from_texts_basic(self):
        retriever = KnowledgeRetriever()
        docs = retriever.retrieve_from_texts(["텍스트1", "텍스트2"])
        assert len(docs) == 2
        assert docs[0].content == "텍스트1"
        assert docs[0].source == "user_upload"
        assert docs[0].relevance == 1.0

    def test_retrieve_from_texts_caps_at_max_docs(self):
        retriever = KnowledgeRetriever()
        texts = [f"텍스트{i}" for i in range(10)]
        docs = retriever.retrieve_from_texts(texts)
        assert len(docs) == 3  # _MAX_DOCS = 3

    def test_retrieve_from_texts_truncates_content(self):
        retriever = KnowledgeRetriever()
        long_text = "x" * 1000
        docs = retriever.retrieve_from_texts([long_text])
        assert len(docs[0].content) == 500  # _MAX_CHARS = 500

    def test_retrieve_from_texts_custom_source(self):
        retriever = KnowledgeRetriever()
        docs = retriever.retrieve_from_texts(["내용"], source="rag")
        assert docs[0].source == "rag"

    def test_retrieve_from_texts_empty_input(self):
        retriever = KnowledgeRetriever()
        docs = retriever.retrieve_from_texts([])
        assert docs == []


# ── WebSearchTool ─────────────────────────────────────────

class TestWebSearchToolNoKey:
    """TAVILY_API_KEY 없을 때."""

    def setup_method(self):
        with patch.dict(os.environ, {}, clear=True):
            # TAVILY_API_KEY 없음 → _client = None
            if "TAVILY_API_KEY" in os.environ:
                del os.environ["TAVILY_API_KEY"]

    def test_search_returns_empty_without_client(self):
        tool = WebSearchTool()
        tool._client = None
        result = tool.search("쿼리")
        assert result == []

    def test_search_signals_returns_empty_without_client(self):
        tool = WebSearchTool()
        tool._client = None
        result = tool.search_signals("쿼리")
        assert result == []


class TestWebSearchToolInit:
    def test_init_with_api_key_sets_client(self):
        mock_tavily = MagicMock()
        mock_client_instance = MagicMock()
        mock_tavily.TavilyClient.return_value = mock_client_instance

        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}), \
             patch.dict("sys.modules", {"tavily": mock_tavily}):
            tool = WebSearchTool()

        assert tool._client is mock_client_instance
        mock_tavily.TavilyClient.assert_called_once_with(api_key="test-key")

    def test_init_without_api_key_no_client(self):
        env = {k: v for k, v in os.environ.items() if k != "TAVILY_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            tool = WebSearchTool()
        assert tool._client is None


class TestWebSearchToolWithClient:
    """Tavily 클라이언트 mock."""

    def _make_tool_with_mock_client(self):
        tool = WebSearchTool()
        tool._client = MagicMock()
        return tool

    def test_search_returns_documents(self):
        tool = self._make_tool_with_mock_client()
        tool._client.search.return_value = {
            "results": [
                {"content": "검색 내용1", "score": 0.9, "url": "https://example.com", "title": "제목1"},
                {"content": "검색 내용2", "score": 0.7, "url": "https://example2.com", "title": "제목2"},
            ]
        }
        docs = tool.search("쿼리")
        assert len(docs) == 2
        assert docs[0].content == "검색 내용1"
        assert docs[0].source == "web"
        assert docs[0].relevance == 0.9
        assert docs[0].metadata["url"] == "https://example.com"

    def test_search_uses_snippet_fallback(self):
        tool = self._make_tool_with_mock_client()
        tool._client.search.return_value = {
            "results": [{"snippet": "스니펫 내용", "score": 0.5}]
        }
        docs = tool.search("쿼리")
        assert docs[0].content == "스니펫 내용"

    def test_search_truncates_content(self):
        tool = self._make_tool_with_mock_client()
        tool._client.search.return_value = {
            "results": [{"content": "x" * 1000, "score": 0.5}]
        }
        docs = tool.search("쿼리")
        assert len(docs[0].content) == 500

    def test_search_handles_exception(self):
        tool = self._make_tool_with_mock_client()
        tool._client.search.side_effect = Exception("네트워크 오류")
        docs = tool.search("쿼리")
        assert docs == []

    def test_search_signals_alternates_signal_type(self):
        tool = self._make_tool_with_mock_client()
        tool._client.search.return_value = {
            "results": [
                {"content": "결과0", "score": 0.8},
                {"content": "결과1", "score": 0.6},
                {"content": "결과2", "score": 0.7},
            ]
        }
        signals = tool.search_signals("쿼리")
        assert signals[0].signal_type == "trend"     # i=0, even
        assert signals[1].signal_type == "edge_case"  # i=1, odd
        assert signals[2].signal_type == "trend"     # i=2, even

    def test_search_signals_skips_empty_content(self):
        tool = self._make_tool_with_mock_client()
        tool._client.search.return_value = {
            "results": [
                {"content": "", "score": 0.5},
                {"content": "유효한 내용", "score": 0.8},
            ]
        }
        signals = tool.search_signals("쿼리")
        assert len(signals) == 1
        assert signals[0].content == "유효한 내용"

    def test_search_signals_handles_exception(self):
        tool = self._make_tool_with_mock_client()
        tool._client.search.side_effect = Exception("오류")
        signals = tool.search_signals("쿼리")
        assert signals == []

    def test_search_signals_strength_from_score(self):
        tool = self._make_tool_with_mock_client()
        tool._client.search.return_value = {
            "results": [{"content": "내용", "score": 0.9}]
        }
        signals = tool.search_signals("쿼리")
        assert signals[0].strength == 0.9

    def test_search_empty_results(self):
        tool = self._make_tool_with_mock_client()
        tool._client.search.return_value = {"results": []}
        docs = tool.search("쿼리")
        assert docs == []

    def test_search_signals_empty_results(self):
        tool = self._make_tool_with_mock_client()
        tool._client.search.return_value = {"results": []}
        signals = tool.search_signals("쿼리")
        assert signals == []
