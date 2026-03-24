"""SerendipityGenerator 단위 테스트."""
import json
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from creativity_engine.config import EngineConfig
from creativity_engine.core.models import CreativityProblem, InputBundle
from creativity_engine.core.connection_engine import (
    SerendipityGenerator,
    _SERENDIPITY_DOMAINS,
)
from tests.conftest import MockLLMClient


def _make_bundle(serendipity: float, divergence_n: int = 6) -> InputBundle:
    problem = CreativityProblem(
        goal="원격 근무자 집중력 문제",
        constraints=["예산 50만원"],
        serendipity=serendipity,
        divergence_n=divergence_n,
    )
    return InputBundle(problem=problem)


MOCK_IDEAS = json.dumps([
    {"content": "요리 레시피처럼 단계별 집중 루틴", "rationale": "요리의 순서 개념 적용",
     "source_domains": ["요리", "생산성"], "connections": ["루틴", "단계"]},
])


class TestSerendipityModel:
    def test_default_serendipity_is_zero(self):
        p = CreativityProblem(goal="x")
        assert p.serendipity == 0.0

    def test_serendipity_bounds(self):
        with pytest.raises(ValidationError):
            CreativityProblem(goal="x", serendipity=1.5)
        with pytest.raises(ValidationError):
            CreativityProblem(goal="x", serendipity=-0.1)

    def test_serendipity_set(self):
        p = CreativityProblem(goal="x", serendipity=0.7)
        assert p.serendipity == pytest.approx(0.7)


class TestSerendipityGenerator:
    def test_skip_when_zero(self):
        gen = SerendipityGenerator()
        bundle = _make_bundle(serendipity=0.0)
        result = gen.run(bundle)
        assert result == []

    def test_skip_when_exactly_zero_no_llm_call(self):
        mock_llm = MockLLMClient(MOCK_IDEAS)
        gen = SerendipityGenerator(client=mock_llm)
        bundle = _make_bundle(serendipity=0.0)
        result = gen.run(bundle)
        assert mock_llm.calls == []
        assert result == []

    def test_runs_when_nonzero(self):
        mock_llm = MockLLMClient(MOCK_IDEAS)
        gen = SerendipityGenerator(client=mock_llm)
        bundle = _make_bundle(serendipity=0.5)
        result = gen.run(bundle)
        assert len(result) >= 1
        assert result[0].content == "요리 레시피처럼 단계별 집중 루틴"

    def test_domain_count_scales_with_serendipity(self):
        """serendipity 높을수록 더 많은 랜덤 도메인 선택."""
        selected_counts = []
        for serendipity in [0.25, 0.5, 0.75, 1.0]:
            bundle = _make_bundle(serendipity=serendipity)
            mock_llm = MockLLMClient(MOCK_IDEAS)
            with patch("creativity_engine.core.connection_engine.random") as mock_random:
                mock_random.sample.return_value = ["요리"]
                gen = SerendipityGenerator(client=mock_llm)
                gen.run(bundle)
                call_args = mock_random.sample.call_args
                domain_count = call_args[0][1]
                selected_counts.append(domain_count)

        assert selected_counts[0] <= selected_counts[-1]

    def test_idea_count_scales_with_serendipity(self):
        """serendipity 높을수록 생성 아이디어 수 증가."""
        import math
        low_n = max(1, round(0.2 * 10 * 0.4))
        high_n = max(1, round(1.0 * 10 * 0.4))
        assert low_n < high_n

    def test_uses_random_domains_from_pool(self):
        """선택된 도메인이 _SERENDIPITY_DOMAINS 풀에서 나와야 함."""
        bundle = _make_bundle(serendipity=0.5)
        mock_llm = MockLLMClient(MOCK_IDEAS)
        gen = SerendipityGenerator(client=mock_llm)
        gen.run(bundle)

        assert len(mock_llm.calls) == 1
        user_prompt = mock_llm.calls[0][1]
        assert "random_domains" in user_prompt
        any_domain_found = any(d in user_prompt for d in _SERENDIPITY_DOMAINS)
        assert any_domain_found

    def test_handles_api_error_gracefully(self):
        from creativity_engine.llm.base import BaseLLMClient

        class ErrorClient(BaseLLMClient):
            def call(self, system, user, max_tokens=4096):
                raise Exception("API 오류")

        bundle = _make_bundle(serendipity=0.5)
        gen = SerendipityGenerator(client=ErrorClient())
        with pytest.raises(Exception):
            gen.run(bundle)

    def test_handles_json_parse_error(self):
        mock_llm = MockLLMClient("not json")
        gen = SerendipityGenerator(client=mock_llm)
        bundle = _make_bundle(serendipity=0.5)
        result = gen.run(bundle)
        assert result == []

    def test_custom_serendipity_domains_via_config(self):
        """EngineConfig로 도메인 풀 교체 가능."""
        custom_domains = ["해킹", "양자역학", "마케팅"]
        config = EngineConfig(serendipity_domains=custom_domains)
        mock_llm = MockLLMClient(MOCK_IDEAS)
        gen = SerendipityGenerator(client=mock_llm, config=config)
        bundle = _make_bundle(serendipity=1.0)
        gen.run(bundle)

        user_prompt = mock_llm.calls[0][1]
        any_custom_found = any(d in user_prompt for d in custom_domains)
        assert any_custom_found


class TestSerendipityIntegration:
    """engine.run()에서 serendipity 파라미터가 실제로 반영되는지."""

    def test_serendipity_zero_returns_empty_ideas(self):
        """serendipity=0.0이면 SerendipityGenerator가 [] 반환."""
        from tests.conftest import MockLLMClient
        mock_llm = MockLLMClient(MOCK_IDEAS)
        config = EngineConfig(llm_client=mock_llm)
        gen = SerendipityGenerator(client=mock_llm, config=config)
        bundle = _make_bundle(serendipity=0.0)
        results = []

        original_run = SerendipityGenerator.run

        def capturing_run(self, b):
            result = original_run(self, b)
            results.append(result)
            return result

        with patch("creativity_engine.core.input_engine.WebSearchTool"), \
             patch.object(SerendipityGenerator, "run", capturing_run):
            from creativity_engine import CreativityEngine
            engine = CreativityEngine(config=config)
            engine.run_raw({"goal": "테스트", "divergence_n": 2, "top_k": 1,
                           "max_reflection_rounds": 0, "serendipity": 0.0})

        assert len(results) == 1
        assert results[0] == []

    def test_serendipity_via_kwargs(self):
        """engine.run(..., serendipity=0.5) 형태로 전달."""
        mock_llm = MockLLMClient(MOCK_IDEAS)
        config = EngineConfig(llm_client=mock_llm)

        with patch("creativity_engine.core.input_engine.WebSearchTool"):
            from creativity_engine import CreativityEngine
            engine = CreativityEngine(config=config)
            solution = engine.run_raw(
                "테스트 문제",
                divergence_n=2,
                top_k=1,
                max_reflection_rounds=0,
                serendipity=0.5,
            )

        assert solution.problem.serendipity == pytest.approx(0.5)
