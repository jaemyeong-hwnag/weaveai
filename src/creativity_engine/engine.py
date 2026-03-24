from __future__ import annotations

import logging
from typing import Any

from .adapters.base import DomainAdapter
from .adapters.general import GeneralAdapter
from .core.input_engine import InputEngine
from .core.connection_engine import ConnectionEngine
from .core.output_engine import OutputEngine
from .core.models import Solution

logger = logging.getLogger(__name__)


class CreativityEngine:
    """
    Creativity Engine 메인 오케스트레이터.

    사용법:
        engine = CreativityEngine(adapter=GeneralAdapter())
        result = engine.run("원격 근무자의 집중력 저하 문제를 해결하고 싶다")
    """

    def __init__(self, adapter: DomainAdapter | None = None) -> None:
        self.adapter = adapter or GeneralAdapter()
        self._input_engine = InputEngine()
        self._connection_engine = ConnectionEngine()
        self._output_engine = OutputEngine()

    def run(self, raw: dict | str, **kwargs) -> Any:
        """
        6단계 파이프라인 실행 후 도메인 포맷으로 렌더링된 결과 반환.

        kwargs로 divergence_n, top_k 등을 오버라이드 가능.
        """
        # kwargs를 raw dict에 병합
        if kwargs:
            if isinstance(raw, str):
                raw = {"goal": raw, **kwargs}
            else:
                raw = {**raw, **kwargs}

        solution = self._run_pipeline(raw)
        return self.adapter.render_solution(solution)

    def run_raw(self, raw: dict | str, **kwargs) -> Solution:
        """
        render_solution 없이 Solution 객체 그대로 반환.
        디버깅·테스트용.
        """
        if kwargs:
            if isinstance(raw, str):
                raw = {"goal": raw, **kwargs}
            else:
                raw = {**raw, **kwargs}

        return self._run_pipeline(raw)

    def _run_pipeline(self, raw: dict | str) -> Solution:
        # Step 1: 도메인 입력 → CreativityProblem
        problem = self.adapter.format_problem(raw)

        # Step 2: 도메인 특화 검증 (경고 출력)
        warnings = self.adapter.validate_problem(problem)
        for w in warnings:
            logger.warning("[%s] %s", self.adapter.get_domain_name(), w)

        # Step 3: InputEngine → InputBundle
        bundle = self._input_engine.run(problem)

        # Step 4: ConnectionEngine → IdeaSet
        idea_set = self._connection_engine.run(bundle)

        # Step 5: OutputEngine → Solution
        solution = self._output_engine.run(idea_set)

        return solution
