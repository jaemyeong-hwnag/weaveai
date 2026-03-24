"""CreativityEngine 통합 테스트 — 모든 레이어 mock."""
import json
from unittest.mock import MagicMock, patch

import pytest

from creativity_engine import CreativityEngine, GeneralAdapter, LegalAdapter
from creativity_engine.core.models import Solution


def _make_claude_response(text: str):
    mock = MagicMock()
    mock.content = [MagicMock(text=text)]
    return mock


MOCK_IDEAS = json.dumps([
    {"content": "아이디어A", "rationale": "이유", "source_domains": ["심리학"], "connections": ["집중력"]},
    {"content": "아이디어B", "rationale": "이유", "source_domains": ["게임"], "connections": ["보상"]},
])
MOCK_SOLUTION = "구체적인 솔루션 텍스트"
MOCK_REFLECTION = "평가: 적절함\n신뢰도: 0.75"


class TestCreativityEngineRun:
    def _patch_claude(self, responses):
        """여러 Claude 응답을 순서대로 반환하는 mock."""
        mock = MagicMock()
        mock.messages.create.side_effect = [
            _make_claude_response(r) for r in responses
        ]
        return mock

    def test_run_returns_dict_for_general_adapter(self):
        responses = [MOCK_IDEAS, MOCK_IDEAS, MOCK_IDEAS, MOCK_IDEAS, MOCK_SOLUTION, MOCK_REFLECTION, MOCK_REFLECTION]
        with patch("creativity_engine.core.connection_engine._client", self._patch_claude(responses[:4])), \
             patch("creativity_engine.core.output_engine._client", self._patch_claude(responses[4:])), \
             patch("creativity_engine.core.input_engine.WebSearchTool"):
            engine = CreativityEngine(adapter=GeneralAdapter())
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
        responses = [MOCK_IDEAS, MOCK_IDEAS, MOCK_IDEAS, MOCK_IDEAS, MOCK_SOLUTION]
        with patch("creativity_engine.core.connection_engine._client", self._patch_claude(responses[:4])), \
             patch("creativity_engine.core.output_engine._client", self._patch_claude(responses[4:])), \
             patch("creativity_engine.core.input_engine.WebSearchTool"):
            engine = CreativityEngine()
            solution = engine.run_raw({
                "goal": "테스트",
                "divergence_n": 2,
                "top_k": 1,
                "max_reflection_rounds": 0,
            })

        assert isinstance(solution, Solution)
        assert solution.confidence >= 0.0

    def test_run_with_string_input(self):
        responses = [MOCK_IDEAS, MOCK_IDEAS, MOCK_IDEAS, MOCK_IDEAS, MOCK_SOLUTION]
        with patch("creativity_engine.core.connection_engine._client", self._patch_claude(responses[:4])), \
             patch("creativity_engine.core.output_engine._client", self._patch_claude(responses[4:])), \
             patch("creativity_engine.core.input_engine.WebSearchTool"):
            engine = CreativityEngine()
            result = engine.run("단순 문자열 입력", divergence_n=2, top_k=1, max_reflection_rounds=0)

        assert isinstance(result, dict)

    def test_default_adapter_is_general(self):
        engine = CreativityEngine()
        assert isinstance(engine.adapter, GeneralAdapter)

    def test_custom_adapter_used(self):
        engine = CreativityEngine(adapter=LegalAdapter())
        assert isinstance(engine.adapter, LegalAdapter)

    def test_kwargs_override_raw(self):
        """kwargs가 raw dict에 병합되어야 함."""
        responses = [MOCK_IDEAS, MOCK_IDEAS, MOCK_IDEAS, MOCK_IDEAS, MOCK_SOLUTION]
        with patch("creativity_engine.core.connection_engine._client", self._patch_claude(responses[:4])), \
             patch("creativity_engine.core.output_engine._client", self._patch_claude(responses[4:])), \
             patch("creativity_engine.core.input_engine.WebSearchTool"):
            engine = CreativityEngine()
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
        responses = [MOCK_IDEAS, MOCK_IDEAS, MOCK_IDEAS, MOCK_IDEAS, MOCK_SOLUTION]
        with patch("creativity_engine.core.connection_engine._client", self._patch_claude(responses[:4])), \
             patch("creativity_engine.core.output_engine._client", self._patch_claude(responses[4:])), \
             patch("creativity_engine.core.input_engine.WebSearchTool"), \
             caplog.at_level(logging.WARNING):
            engine = CreativityEngine(adapter=LegalAdapter())
            engine.run_raw({
                "facts": "계약 분쟁",
                "client_position": "A사",
                "desired_outcome": "승소",
                # jurisdiction 없음 → 경고 발생
                "divergence_n": 2,
                "top_k": 1,
                "max_reflection_rounds": 0,
            })
        assert any("관할" in r.message for r in caplog.records)
