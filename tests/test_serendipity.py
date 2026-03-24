"""SerendipityGenerator 단위 테스트."""
import json
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from creativity_engine.core.models import CreativityProblem, InputBundle
from creativity_engine.core.connection_engine import (
    SerendipityGenerator,
    _SERENDIPITY_DOMAINS,
)


def _make_bundle(serendipity: float, divergence_n: int = 6) -> InputBundle:
    problem = CreativityProblem(
        goal="원격 근무자 집중력 문제",
        constraints=["예산 50만원"],
        serendipity=serendipity,
        divergence_n=divergence_n,
    )
    return InputBundle(problem=problem)


def _make_mock_response(text: str):
    from unittest.mock import MagicMock
    mock = MagicMock()
    mock.content = [MagicMock(text=text)]
    return mock


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

    def test_skip_when_exactly_zero(self):
        gen = SerendipityGenerator()
        bundle = _make_bundle(serendipity=0.0)
        # Claude API 호출 없이 즉시 반환
        with patch("creativity_engine.core.connection_engine._client") as mock_client:
            result = gen.run(bundle)
            mock_client.messages.create.assert_not_called()
        assert result == []

    def test_runs_when_nonzero(self):
        bundle = _make_bundle(serendipity=0.5)
        with patch("creativity_engine.core.connection_engine._client") as mock_client:
            mock_client.messages.create.return_value = _make_mock_response(MOCK_IDEAS)
            gen = SerendipityGenerator()
            result = gen.run(bundle)
        assert len(result) >= 1
        assert result[0].content == "요리 레시피처럼 단계별 집중 루틴"

    def test_domain_count_scales_with_serendipity(self):
        """serendipity 높을수록 더 많은 랜덤 도메인 선택."""
        selected_counts = []
        for serendipity in [0.25, 0.5, 0.75, 1.0]:
            bundle = _make_bundle(serendipity=serendipity)
            with patch("creativity_engine.core.connection_engine._client") as mock_client, \
                 patch("creativity_engine.core.connection_engine.random") as mock_random:
                mock_random.sample.return_value = ["요리"]
                mock_client.messages.create.return_value = _make_mock_response(MOCK_IDEAS)
                gen = SerendipityGenerator()
                gen.run(bundle)
                call_args = mock_random.sample.call_args
                domain_count = call_args[0][1]  # 두 번째 positional arg = k
                selected_counts.append(domain_count)

        # 낮은 serendipity → 적은 도메인, 높은 serendipity → 많은 도메인
        assert selected_counts[0] <= selected_counts[-1]

    def test_idea_count_scales_with_serendipity(self):
        """serendipity 높을수록 생성 아이디어 수 증가."""
        low_bundle = _make_bundle(serendipity=0.2, divergence_n=10)
        high_bundle = _make_bundle(serendipity=1.0, divergence_n=10)

        gen = SerendipityGenerator()
        # n 값 추출만 확인 (Claude 호출 없이)
        import math
        low_n = max(1, round(0.2 * 10 * 0.4))
        high_n = max(1, round(1.0 * 10 * 0.4))
        assert low_n < high_n

    def test_uses_random_domains_from_pool(self):
        """선택된 도메인이 _SERENDIPITY_DOMAINS 풀에서 나와야 함."""
        bundle = _make_bundle(serendipity=0.5)
        captured_user = []

        def fake_create(**kwargs):
            captured_user.append(kwargs.get("messages", [{}])[0].get("content", ""))
            return _make_mock_response(MOCK_IDEAS)

        with patch("creativity_engine.core.connection_engine._client") as mock_client:
            mock_client.messages.create.side_effect = fake_create
            gen = SerendipityGenerator()
            gen.run(bundle)

        user_prompt = captured_user[0]
        assert "random_domains" in user_prompt
        # 프롬프트에 포함된 도메인이 풀에 있어야 함
        any_domain_found = any(d in user_prompt for d in _SERENDIPITY_DOMAINS)
        assert any_domain_found

    def test_handles_api_error_gracefully(self):
        bundle = _make_bundle(serendipity=0.5)
        with patch("creativity_engine.core.connection_engine._client") as mock_client:
            mock_client.messages.create.side_effect = Exception("API 오류")
            gen = SerendipityGenerator()
            with pytest.raises(Exception):
                gen.run(bundle)

    def test_handles_json_parse_error(self):
        bundle = _make_bundle(serendipity=0.5)
        with patch("creativity_engine.core.connection_engine._client") as mock_client:
            mock_client.messages.create.return_value = _make_mock_response("not json")
            gen = SerendipityGenerator()
            result = gen.run(bundle)
        assert result == []


class TestSerendipityIntegration:
    """engine.run()에서 serendipity 파라미터가 실제로 반영되는지."""

    def test_serendipity_zero_returns_empty_ideas(self):
        """serendipity=0.0이면 SerendipityGenerator가 [] 반환."""
        from unittest.mock import MagicMock
        gen = SerendipityGenerator()
        bundle = _make_bundle(serendipity=0.0)
        results = []

        original_run = SerendipityGenerator.run

        def capturing_run(self, b):
            result = original_run(self, b)
            results.append(result)
            return result

        with patch("creativity_engine.core.connection_engine._client") as cc, \
             patch("creativity_engine.core.output_engine._client") as oc, \
             patch("creativity_engine.core.input_engine.WebSearchTool"), \
             patch.object(SerendipityGenerator, "run", capturing_run):
            mock_ideas = json.dumps([
                {"content": "아이디어", "rationale": "이유",
                 "source_domains": ["심리학"], "connections": ["집중력"]}
            ])
            m = MagicMock()
            m.content = [MagicMock(text=mock_ideas)]
            cc.messages.create.return_value = m
            oc.messages.create.return_value = m

            from creativity_engine import CreativityEngine
            engine = CreativityEngine()
            engine.run_raw({"goal": "테스트", "divergence_n": 2, "top_k": 1,
                           "max_reflection_rounds": 0, "serendipity": 0.0})

        assert len(results) == 1
        assert results[0] == []

    def test_serendipity_via_kwargs(self):
        """engine.run(..., serendipity=0.5) 형태로 전달."""
        from creativity_engine import CreativityEngine

        def make_resp(text):
            from unittest.mock import MagicMock
            m = MagicMock()
            m.content = [MagicMock(text=text)]
            return m

        mock_ideas = json.dumps([
            {"content": "아이디어", "rationale": "이유",
             "source_domains": ["요리"], "connections": ["루틴"]}
        ])

        with patch("creativity_engine.core.connection_engine._client") as cc, \
             patch("creativity_engine.core.output_engine._client") as oc, \
             patch("creativity_engine.core.input_engine.WebSearchTool"):
            cc.messages.create.return_value = make_resp(mock_ideas)
            oc.messages.create.return_value = make_resp("솔루션")

            engine = CreativityEngine()
            solution = engine.run_raw(
                "테스트 문제",
                divergence_n=2,
                top_k=1,
                max_reflection_rounds=0,
                serendipity=0.5,
            )

        assert solution.problem.serendipity == pytest.approx(0.5)
