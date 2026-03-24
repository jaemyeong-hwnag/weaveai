"""CreativityEngine 통합 테스트 — MockLLMClient 주입."""
import json
from unittest.mock import patch

import pytest

from creativity_engine import CreativityEngine, GeneralAdapter, LegalAdapter
from creativity_engine.config import EngineConfig
from creativity_engine.core.models import Solution
from tests.conftest import MockLLMClient


MOCK_IDEAS = json.dumps([
    {"content": "아이디어A", "rationale": "이유", "source_domains": ["심리학"], "connections": ["집중력"]},
    {"content": "아이디어B", "rationale": "이유", "source_domains": ["게임"], "connections": ["보상"]},
])
MOCK_SOLUTION = "구체적인 솔루션 텍스트"
MOCK_REFLECTION = "평가: 적절함\n신뢰도: 0.75"


def _make_config(responses: list[str]) -> tuple[EngineConfig, MockLLMClient]:
    """순서대로 응답을 반환하는 MockLLMClient가 담긴 EngineConfig 반환."""
    idx = [0]

    class SeqLLMClient(MockLLMClient):
        def call(self, system, user, max_tokens=4096):
            val = responses[idx[0]] if idx[0] < len(responses) else responses[-1]
            idx[0] += 1
            return val

    client = SeqLLMClient()
    config = EngineConfig(llm_client=client)
    return config, client


class TestCreativityEngineRun:
    def test_run_returns_dict_for_general_adapter(self):
        responses = [MOCK_IDEAS] * 4 + [MOCK_SOLUTION, MOCK_REFLECTION, MOCK_REFLECTION]
        config, _ = _make_config(responses)
        with patch("creativity_engine.core.input_engine.WebSearchTool"):
            engine = CreativityEngine(adapter=GeneralAdapter(), config=config)
            result = engine.run({
                "goal": "테스트 문제",
                "divergence_n": 2,
                "top_k": 1,
                "max_reflection_rounds": 0,
            })

        assert isinstance(result, dict)
        assert "solution" in result
        assert "top_ideas" in result
        assert "confidence" in result

    def test_run_raw_returns_solution_object(self):
        responses = [MOCK_IDEAS] * 4 + [MOCK_SOLUTION]
        config, _ = _make_config(responses)
        with patch("creativity_engine.core.input_engine.WebSearchTool"):
            engine = CreativityEngine(config=config)
            solution = engine.run_raw({
                "goal": "테스트",
                "divergence_n": 2,
                "top_k": 1,
                "max_reflection_rounds": 0,
            })

        assert isinstance(solution, Solution)
        assert solution.confidence >= 0.0

    def test_run_with_string_input(self):
        responses = [MOCK_IDEAS] * 4 + [MOCK_SOLUTION]
        config, _ = _make_config(responses)
        with patch("creativity_engine.core.input_engine.WebSearchTool"):
            engine = CreativityEngine(config=config)
            result = engine.run("단순 문자열 입력", divergence_n=2, top_k=1, max_reflection_rounds=0)

        assert isinstance(result, dict)

    def test_default_adapter_is_general(self):
        engine = CreativityEngine()
        assert isinstance(engine.adapter, GeneralAdapter)

    def test_custom_adapter_used(self):
        engine = CreativityEngine(adapter=LegalAdapter())
        assert isinstance(engine.adapter, LegalAdapter)

    def test_kwargs_override_raw(self):
        responses = [MOCK_IDEAS] * 4 + [MOCK_SOLUTION]
        config, _ = _make_config(responses)
        with patch("creativity_engine.core.input_engine.WebSearchTool"):
            engine = CreativityEngine(config=config)
            solution = engine.run_raw(
                {"goal": "목표"},
                divergence_n=2,
                top_k=1,
                max_reflection_rounds=0,
            )
        assert solution.problem.divergence_n == 2
        assert solution.problem.top_k == 1

    def test_validation_warnings_logged(self, caplog):
        import logging
        responses = [MOCK_IDEAS] * 4 + [MOCK_SOLUTION]
        config, _ = _make_config(responses)
        with patch("creativity_engine.core.input_engine.WebSearchTool"), \
             caplog.at_level(logging.WARNING):
            engine = CreativityEngine(adapter=LegalAdapter(), config=config)
            engine.run_raw({
                "facts": "계약 분쟁",
                "client_position": "A사",
                "desired_outcome": "승소",
                "divergence_n": 2,
                "top_k": 1,
                "max_reflection_rounds": 0,
            })
        assert any("관할" in r.message for r in caplog.records)
