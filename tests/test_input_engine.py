"""input_engine 단위 테스트 — 외부 I/O mock."""
from unittest.mock import MagicMock, patch

import pytest

from creativity_engine.core.input_engine import ContextBuilder, InputEngine, SignalCollector
from creativity_engine.core.models import CreativityProblem, Document, InputBundle, Signal


class TestContextBuilder:
    def setup_method(self):
        self.builder = ContextBuilder()

    def test_basic_goal(self):
        p = CreativityProblem(goal="테스트 목표")
        result = self.builder.build(p)
        assert "테스트 목표" in result

    def test_with_constraints(self):
        p = CreativityProblem(goal="목표", constraints=["제약1", "제약2"])
        result = self.builder.build(p)
        assert "제약1" in result
        assert "제약2" in result

    def test_with_context(self):
        p = CreativityProblem(goal="목표", context={"team_size": 5})
        result = self.builder.build(p)
        assert "team_size" in result

    def test_with_domain_hint(self):
        p = CreativityProblem(goal="목표", domain_hint="legal")
        result = self.builder.build(p)
        assert "legal" in result

    def test_no_extra_sections_when_empty(self):
        p = CreativityProblem(goal="목표")
        result = self.builder.build(p)
        assert "제약" not in result
        assert "맥락" not in result


class TestSignalCollector:
    def test_collect_returns_signals_from_search(self, basic_problem):
        with patch("creativity_engine.core.input_engine.WebSearchTool") as MockTool:
            instance = MockTool.return_value
            instance.search_signals.return_value = [
                Signal(content="트렌드 신호", signal_type="trend", strength=0.7)
            ]
            collector = SignalCollector()
            collector._search = instance
            signals = collector.collect(basic_problem)

        assert any(s.content == "트렌드 신호" for s in signals)

    def test_collect_adds_constraint_signals(self, basic_problem):
        with patch("creativity_engine.core.input_engine.WebSearchTool") as MockTool:
            instance = MockTool.return_value
            instance.search_signals.return_value = []
            collector = SignalCollector()
            collector._search = instance
            signals = collector.collect(basic_problem)

        # 제약 조건 → counter_example 신호 추가
        counter_signals = [s for s in signals if s.signal_type == "counter_example"]
        assert len(counter_signals) > 0

    def test_collect_returns_empty_on_error(self, basic_problem):
        with patch("creativity_engine.core.input_engine.WebSearchTool") as MockTool:
            instance = MockTool.return_value
            instance.search_signals.side_effect = Exception("네트워크 오류")
            collector = SignalCollector()
            collector._search = instance
            signals = collector.collect(basic_problem)

        assert signals == []


class TestInputEngine:
    def test_run_returns_bundle(self, basic_problem):
        with patch("creativity_engine.core.input_engine.KnowledgeRetriever") as MockRet, \
             patch("creativity_engine.core.input_engine.WebSearchTool"):
            mock_ret = MockRet.return_value
            mock_ret.retrieve.return_value = [
                Document(content="지식", source="web", relevance=0.8)
            ]
            engine = InputEngine()
            engine._retriever = mock_ret
            bundle = engine.run(basic_problem)

        assert isinstance(bundle, InputBundle)
        assert bundle.problem == basic_problem
        assert len(bundle.knowledge) == 1
        assert "목표" in bundle.context_summary

    def test_run_returns_bundle_on_retrieval_failure(self, basic_problem):
        with patch("creativity_engine.core.input_engine.KnowledgeRetriever") as MockRet, \
             patch("creativity_engine.core.input_engine.WebSearchTool"):
            mock_ret = MockRet.return_value
            mock_ret.retrieve.side_effect = Exception("검색 실패")
            engine = InputEngine()
            engine._retriever = mock_ret
            bundle = engine.run(basic_problem)

        # 실패해도 빈 InputBundle 반환 (파이프라인 중단 없음)
        assert isinstance(bundle, InputBundle)
        assert bundle.knowledge == []

    def test_metadata_contains_counts(self, basic_problem):
        with patch("creativity_engine.core.input_engine.KnowledgeRetriever") as MockRet, \
             patch("creativity_engine.core.input_engine.WebSearchTool"):
            mock_ret = MockRet.return_value
            mock_ret.retrieve.return_value = []
            engine = InputEngine()
            engine._retriever = mock_ret
            bundle = engine.run(basic_problem)

        assert "knowledge_count" in bundle.metadata
        assert "signal_count" in bundle.metadata
