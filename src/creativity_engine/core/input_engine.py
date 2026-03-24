from __future__ import annotations

import logging

from ..config import EngineConfig
from ..core.models import CreativityProblem, Document, InputBundle, Signal
from ..tools.retriever import KnowledgeRetriever
from ..tools.web_search import WebSearchTool

logger = logging.getLogger(__name__)


class ContextBuilder:
    """CreativityProblem → LLM 프롬프트용 요약 텍스트 변환. API 호출 없음."""

    def build(self, problem: CreativityProblem) -> str:
        lines = [f"목표: {problem.goal}"]

        if problem.constraints:
            lines.append("제약: " + ", ".join(problem.constraints))

        if problem.context:
            ctx_parts = [f"{k}={v}" for k, v in problem.context.items()]
            lines.append("맥락: " + ", ".join(ctx_parts))

        if problem.domain_hint:
            lines.append(f"도메인: {problem.domain_hint}")

        return "\n".join(lines)


class SignalCollector:
    """Tavily 웹 검색으로 엣지케이스·트렌드 신호 수집. 실패 시 빈 리스트 반환."""

    def __init__(self) -> None:
        self._search = WebSearchTool()

    def collect(self, problem: CreativityProblem) -> list[Signal]:
        try:
            signals = self._search.search_signals(
                query=problem.goal,
                max_results=5,
            )
            for constraint in problem.constraints[:2]:
                signals.append(Signal(
                    content=f"제약 조건: {constraint}",
                    signal_type="counter_example",
                    strength=0.8,
                ))
            return signals
        except Exception as e:
            logger.warning("SignalCollector.collect failed: %s", e)
            return []


class InputEngine:
    """
    Input Engine: CreativityProblem → InputBundle.
    모든 컴포넌트 실패 시 빈 InputBundle 반환 (파이프라인 중단 없음).
    """

    def __init__(self, config: EngineConfig | None = None) -> None:
        self._config = config or EngineConfig()
        self._retriever = KnowledgeRetriever()
        self._context_builder = ContextBuilder()
        self._signal_collector = SignalCollector()

    def run(self, problem: CreativityProblem) -> InputBundle:
        knowledge: list[Document] = []
        context_summary: str = ""
        signals: list[Signal] = []

        try:
            knowledge = self._retriever.retrieve(
                query=problem.goal,
                top_k=self._config.max_knowledge_docs,
            )
        except Exception as e:
            logger.warning("KnowledgeRetriever failed: %s", e)

        try:
            context_summary = self._context_builder.build(problem)
        except Exception as e:
            logger.warning("ContextBuilder failed: %s", e)
            context_summary = problem.goal

        try:
            signals = self._signal_collector.collect(problem)
        except Exception as e:
            logger.warning("SignalCollector failed: %s", e)

        return InputBundle(
            problem=problem,
            knowledge=knowledge,
            context_summary=context_summary,
            signals=signals,
            metadata={
                "knowledge_count": len(knowledge),
                "signal_count": len(signals),
            },
        )
