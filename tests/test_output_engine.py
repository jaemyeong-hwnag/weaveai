"""output_engine 단위 테스트 — MockLLMClient 주입."""
import pytest

from creativity_engine.config import EngineConfig
from creativity_engine.core.output_engine import (
    Executor,
    OutputEngine,
    Reflector,
    SolutionFormatter,
    _parse_reflection,
)
from creativity_engine.core.models import Action, ActionType, IdeaSet, Solution


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
    def test_format_returns_tuple(self, sample_idea_set, mock_llm):
        mock_llm.set_return("생성된 솔루션 텍스트")
        formatter = SolutionFormatter(client=mock_llm)
        selected, text = formatter.format(sample_idea_set)

        assert selected.content == sample_idea_set.top_ideas[0].content
        assert text == "생성된 솔루션 텍스트"

    def test_format_fallback_on_api_error(self, sample_idea_set):
        from unittest.mock import MagicMock
        from creativity_engine.llm.base import BaseLLMClient

        class ErrorClient(BaseLLMClient):
            def call(self, system, user, max_tokens=4096):
                raise Exception("API 오류")

        formatter = SolutionFormatter(client=ErrorClient())
        selected, text = formatter.format(sample_idea_set)
        assert text == sample_idea_set.top_ideas[0].content

    def test_format_empty_idea_set(self, basic_problem):
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

    def test_reflect_returns_text_and_confidence(self, sample_idea, sample_idea_set, mock_llm):
        mock_llm.set_return("평가: 좋은 솔루션\n신뢰도: 0.8")
        reflector = Reflector(client=mock_llm)
        reflection, confidence = reflector.reflect(
            solution_text="솔루션",
            selected_idea=sample_idea,
            idea_set=sample_idea_set,
            rounds=1,
        )
        assert reflection is not None
        assert confidence == pytest.approx(0.8)

    def test_reflect_returns_default_on_error(self, sample_idea, sample_idea_set):
        from creativity_engine.llm.base import BaseLLMClient

        class ErrorClient(BaseLLMClient):
            def call(self, system, user, max_tokens=4096):
                raise Exception("API 오류")

        reflector = Reflector(client=ErrorClient())
        reflection, confidence = reflector.reflect(
            solution_text="솔루션",
            selected_idea=sample_idea,
            idea_set=sample_idea_set,
            rounds=1,
        )
        assert reflection is None
        assert confidence == 0.5


class TestOutputEngine:
    def test_run_returns_solution(self, sample_idea_set, mock_llm):
        mock_llm.set_return("평가: 좋은 솔루션\n신뢰도: 0.75")
        config = EngineConfig(llm_client=mock_llm)
        engine = OutputEngine(config=config)
        solution = engine.run(sample_idea_set)

        assert isinstance(solution, Solution)
        assert solution.confidence >= 0.0
        assert solution.confidence <= 1.0
        assert solution.solution_text is not None
        assert solution.selected_idea is not None

    def test_run_zero_reflection_rounds(self, basic_problem, sample_idea_set, mock_llm):
        no_reflection_problem = basic_problem.model_copy(update={"max_reflection_rounds": 0})
        idea_set = sample_idea_set.model_copy(update={"problem": no_reflection_problem})

        mock_llm.set_return("솔루션 텍스트")
        config = EngineConfig(llm_client=mock_llm)
        engine = OutputEngine(config=config)
        solution = engine.run(idea_set)

        assert solution.reflection is None
        assert solution.reflection_rounds == 0
        assert solution.confidence == 0.5

    def test_solution_has_actions(self, sample_idea_set, mock_llm):
        mock_llm.set_return("솔루션")
        config = EngineConfig(llm_client=mock_llm)
        engine = OutputEngine(config=config)
        solution = engine.run(sample_idea_set)

        assert len(solution.actions) > 0
        assert solution.actions[0].type == ActionType.TEXT
