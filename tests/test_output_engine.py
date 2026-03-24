"""output_engine 단위 테스트 — Claude API mock."""
from unittest.mock import MagicMock, patch

import pytest

from creativity_engine.core.output_engine import (
    Executor,
    OutputEngine,
    Reflector,
    SolutionFormatter,
    _parse_reflection,
)
from creativity_engine.core.models import Action, ActionType, Solution


def _make_mock_response(text: str):
    mock = MagicMock()
    mock.content = [MagicMock(text=text)]
    return mock


class TestParseReflection:
    def test_extracts_confidence(self):
        text = "평가: 좋은 솔루션입니다.\n신뢰도: 0.85"
        reflection, confidence = _parse_reflection(text)
        assert confidence == pytest.approx(0.85)
        assert "신뢰도" not in reflection

    def test_default_confidence_on_missing(self):
        _, confidence = _parse_reflection("평가만 있음")
        assert confidence == 0.5

    def test_clamps_confidence(self):
        _, confidence = _parse_reflection("신뢰도: 1.5")
        assert confidence == 1.0


class TestSolutionFormatter:
    def test_format_returns_tuple(self, sample_idea_set):
        with patch("creativity_engine.core.output_engine._client") as mock_client:
            mock_client.messages.create.return_value = _make_mock_response("생성된 솔루션 텍스트")
            formatter = SolutionFormatter()
            selected, text = formatter.format(sample_idea_set)

        assert selected.content == sample_idea_set.top_ideas[0].content
        assert text == "생성된 솔루션 텍스트"

    def test_format_fallback_on_api_error(self, sample_idea_set):
        with patch("creativity_engine.core.output_engine._client") as mock_client:
            mock_client.messages.create.side_effect = Exception("API 오류")
            formatter = SolutionFormatter()
            selected, text = formatter.format(sample_idea_set)

        # API 실패 시 idea content 그대로 사용
        assert text == sample_idea_set.top_ideas[0].content

    def test_format_empty_idea_set(self, basic_problem):
        from creativity_engine.core.models import IdeaSet
        empty_set = IdeaSet(problem=basic_problem)
        formatter = SolutionFormatter()
        selected, text = formatter.format(empty_set)
        assert "생성할 수 없습니다" in text


class TestExecutor:
    def test_text_action_executed(self):
        executor = Executor()
        actions = [Action(type=ActionType.TEXT, payload={"text": "결과물"})]
        result = executor.execute(actions)
        assert result[0].result == "결과물"

    def test_non_text_action_is_stub(self):
        executor = Executor()
        for action_type in [ActionType.SEARCH, ActionType.CODE, ActionType.API, ActionType.CUSTOM]:
            actions = [Action(type=action_type)]
            result = executor.execute(actions)
            assert result[0].result["status"] == "not_implemented"

    def test_multiple_actions(self):
        executor = Executor()
        actions = [
            Action(type=ActionType.TEXT, payload={"text": "텍스트1"}),
            Action(type=ActionType.TEXT, payload={"text": "텍스트2"}),
        ]
        result = executor.execute(actions)
        assert result[0].result == "텍스트1"
        assert result[1].result == "텍스트2"


class TestReflector:
    def test_skip_on_zero_rounds(self, sample_idea, sample_idea_set):
        reflector = Reflector()
        reflection, confidence = reflector.reflect(
            solution_text="솔루션",
            selected_idea=sample_idea,
            idea_set=sample_idea_set,
            rounds=0,
        )
        assert reflection is None
        assert confidence == 0.5

    def test_reflect_returns_text_and_confidence(self, sample_idea, sample_idea_set):
        with patch("creativity_engine.core.output_engine._client") as mock_client:
            mock_client.messages.create.return_value = _make_mock_response(
                "평가: 좋은 솔루션\n신뢰도: 0.8"
            )
            reflector = Reflector()
            reflection, confidence = reflector.reflect(
                solution_text="솔루션",
                selected_idea=sample_idea,
                idea_set=sample_idea_set,
                rounds=1,
            )
        assert reflection is not None
        assert confidence == pytest.approx(0.8)

    def test_reflect_returns_default_on_error(self, sample_idea, sample_idea_set):
        with patch("creativity_engine.core.output_engine._client") as mock_client:
            mock_client.messages.create.side_effect = Exception("API 오류")
            reflector = Reflector()
            reflection, confidence = reflector.reflect(
                solution_text="솔루션",
                selected_idea=sample_idea,
                idea_set=sample_idea_set,
                rounds=1,
            )
        assert reflection is None
        assert confidence == 0.5


class TestOutputEngine:
    def test_run_returns_solution(self, sample_idea_set):
        with patch("creativity_engine.core.output_engine._client") as mock_client:
            mock_client.messages.create.return_value = _make_mock_response(
                "평가: 좋은 솔루션\n신뢰도: 0.75"
            )
            engine = OutputEngine()
            solution = engine.run(sample_idea_set)

        assert isinstance(solution, Solution)
        assert solution.confidence >= 0.0
        assert solution.confidence <= 1.0
        assert solution.solution_text is not None
        assert solution.selected_idea is not None

    def test_run_zero_reflection_rounds(self, basic_problem, sample_idea_set):
        no_reflection_problem = basic_problem.model_copy(update={"max_reflection_rounds": 0})
        from creativity_engine.core.models import IdeaSet
        idea_set = sample_idea_set.model_copy(update={"problem": no_reflection_problem})

        with patch("creativity_engine.core.output_engine._client") as mock_client:
            mock_client.messages.create.return_value = _make_mock_response("솔루션 텍스트")
            engine = OutputEngine()
            solution = engine.run(idea_set)

        assert solution.reflection is None
        assert solution.reflection_rounds == 0
        assert solution.confidence == 0.5  # default

    def test_solution_has_actions(self, sample_idea_set):
        with patch("creativity_engine.core.output_engine._client") as mock_client:
            mock_client.messages.create.return_value = _make_mock_response("솔루션")
            engine = OutputEngine()
            solution = engine.run(sample_idea_set)

        assert len(solution.actions) > 0
        assert solution.actions[0].type == ActionType.TEXT
