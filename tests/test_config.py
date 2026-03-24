"""EngineConfig 및 유연한 아키텍처 테스트."""
import json
from unittest.mock import patch

import pytest

from creativity_engine.config import (
    EngineConfig,
    DEFAULT_SERENDIPITY_DOMAINS,
    DEFAULT_GENERATORS,
)
from creativity_engine.llm.base import BaseLLMClient
from creativity_engine.llm.claude import ClaudeClient
from creativity_engine.core.connection_engine import (
    ConnectionEngine,
    DivergenceGenerator,
    NoveltyScorer,
    SerendipityGenerator,
)
from creativity_engine.core.output_engine import OutputEngine, SolutionFormatter, Reflector
from creativity_engine.core.models import CreativityProblem, InputBundle, IdeaSet, Idea
from tests.conftest import MockLLMClient


# ── EngineConfig 기본값 ──────────────────────────────────

class TestEngineConfigDefaults:
    def test_default_model(self):
        assert EngineConfig().model == "claude-sonnet-4-6"

    def test_default_generators(self):
        cfg = EngineConfig()
        assert set(cfg.enabled_generators) == set(DEFAULT_GENERATORS)

    def test_default_score_weights(self):
        cfg = EngineConfig()
        assert cfg.score_weights["novelty"] == pytest.approx(0.6)
        assert cfg.score_weights["feasibility"] == pytest.approx(0.4)

    def test_default_serendipity_domains(self):
        cfg = EngineConfig()
        assert cfg.serendipity_domains == DEFAULT_SERENDIPITY_DOMAINS

    def test_default_limits(self):
        cfg = EngineConfig()
        assert cfg.max_knowledge_docs == 3
        assert cfg.max_chars == 500
        assert cfg.connection_max_tokens == 4096
        assert cfg.output_max_tokens == 512

    def test_prompt_overrides_empty_by_default(self):
        assert EngineConfig().prompt_overrides == {}

    def test_llm_client_none_by_default(self):
        assert EngineConfig().llm_client is None


# ── LLM 주입 ────────────────────────────────────────────

class TestLLMInjection:
    def test_custom_client_used_in_divergence_generator(self):
        mock_llm = MockLLMClient(json.dumps([
            {"content": "아이디어", "rationale": "이유", "source_domains": ["테스트"], "connections": []}
        ]))
        gen = DivergenceGenerator(client=mock_llm)
        bundle = InputBundle(problem=CreativityProblem(goal="목표", divergence_n=1))
        ideas = gen.run(bundle)

        assert len(ideas) == 1
        assert len(mock_llm.calls) == 1

    def test_custom_client_used_in_connection_engine(self):
        mock_llm = MockLLMClient(json.dumps([
            {"content": "아이디어", "rationale": "이유", "source_domains": ["테스트"], "connections": []}
        ]))
        config = EngineConfig(llm_client=mock_llm)
        engine = ConnectionEngine(config=config)
        bundle = InputBundle(problem=CreativityProblem(goal="목표", divergence_n=1, top_k=1))
        idea_set = engine.run(bundle)

        assert isinstance(idea_set, IdeaSet)
        # mock_llm이 실제로 호출되었는지 확인
        assert len(mock_llm.calls) > 0

    def test_custom_client_used_in_output_engine(self, sample_idea_set):
        mock_llm = MockLLMClient("생성된 솔루션\n신뢰도: 0.9")
        config = EngineConfig(llm_client=mock_llm)
        engine = OutputEngine(config=config)
        solution = engine.run(sample_idea_set)

        assert len(mock_llm.calls) > 0


# ── 활성 제너레이터 설정 ──────────────────────────────────

class TestEnabledGenerators:
    def test_diverge_only_config(self):
        """diverge만 활성화하면 다른 노드 없이 그래프 빌드."""
        mock_llm = MockLLMClient(json.dumps([
            {"content": "아이디어", "rationale": "이유", "source_domains": ["A"], "connections": []}
        ]))
        config = EngineConfig(llm_client=mock_llm, enabled_generators=["diverge"])
        engine = ConnectionEngine(config=config)
        bundle = InputBundle(problem=CreativityProblem(goal="목표", divergence_n=1, top_k=1))
        idea_set = engine.run(bundle)
        assert isinstance(idea_set, IdeaSet)

    def test_serendipity_excluded(self):
        """serendipity 제외 시 SerendipityGenerator 호출 안 됨."""
        call_log = []

        class TrackingLLM(BaseLLMClient):
            def call(self, system, user, max_tokens=4096):
                call_log.append(user)
                return json.dumps([
                    {"content": "아이디어", "rationale": "이유", "source_domains": ["A"], "connections": []}
                ])

        config = EngineConfig(
            llm_client=TrackingLLM(),
            enabled_generators=["diverge", "cross_link"],
        )
        engine = ConnectionEngine(config=config)
        bundle = InputBundle(problem=CreativityProblem(
            goal="목표", divergence_n=1, top_k=1, serendipity=1.0
        ))
        engine.run(bundle)

        # serendipity 관련 프롬프트(random_domains 포함)가 호출되지 않아야 함
        serendipity_calls = [u for u in call_log if "random_domains" in u]
        assert len(serendipity_calls) == 0


# ── 스코어 가중치 설정 ────────────────────────────────────

class TestScoreWeights:
    def test_custom_score_weights_applied(self):
        """custom score_weights가 final_score 계산에 반영되어야 함."""
        idea = Idea(content="x", novelty_score=1.0, feasibility_score=0.0)
        from creativity_engine.core.connection_engine import _calculate_final_score

        # novelty 중심
        score_high_novelty = _calculate_final_score(idea, {"novelty": 0.9, "feasibility": 0.1})
        # feasibility 중심
        score_high_feasibility = _calculate_final_score(idea, {"novelty": 0.1, "feasibility": 0.9})

        # novelty=1.0, feasibility=0.0 이므로 novelty 중심일 때 더 높아야 함
        assert score_high_novelty > score_high_feasibility

    def test_config_score_weights_used_in_scorer(self, basic_problem, sample_ideas):
        """NoveltyScorer가 config의 score_weights를 사용해야 함."""
        mock_scores = json.dumps([
            {"id": idea.id, "novelty_score": 1.0, "feasibility_score": 0.0}
            for idea in sample_ideas
        ])
        mock_llm = MockLLMClient(mock_scores)
        config = EngineConfig(
            llm_client=mock_llm,
            score_weights={"novelty": 0.9, "feasibility": 0.1}
        )
        scorer = NoveltyScorer(client=mock_llm, config=config)
        scored = scorer.run(sample_ideas, basic_problem.goal, basic_problem.constraints)

        # novelty=1.0, feasibility=0.0 → final_score ≈ 0.9
        for idea in scored:
            assert idea.final_score == pytest.approx(0.9)


# ── 프롬프트 오버라이드 ────────────────────────────────────

class TestPromptOverrides:
    def test_diverge_prompt_override(self):
        """prompt_overrides["diverge"]가 DivergenceGenerator에 적용되어야 함."""
        custom_system = "CUSTOM DIVERGE SYSTEM {n}"
        captured = []

        class CaptureLLM(BaseLLMClient):
            def call(self, system, user, max_tokens=4096):
                captured.append(system)
                return "[]"

        config = EngineConfig(
            llm_client=CaptureLLM(),
            prompt_overrides={"diverge": custom_system},
        )
        gen = DivergenceGenerator(client=CaptureLLM(), config=config)
        bundle = InputBundle(problem=CreativityProblem(goal="목표", divergence_n=2))
        gen.run(bundle)

        assert captured[0] == "CUSTOM DIVERGE SYSTEM 2"

    def test_formatter_prompt_override(self, sample_idea_set):
        """prompt_overrides["formatter"]가 SolutionFormatter에 적용되어야 함."""
        custom_formatter = "CUSTOM FORMATTER"
        captured = []

        class CaptureLLM(BaseLLMClient):
            def call(self, system, user, max_tokens=4096):
                captured.append(system)
                return "솔루션"

        config = EngineConfig(prompt_overrides={"formatter": custom_formatter})
        formatter = SolutionFormatter(client=CaptureLLM(), config=config)
        formatter.format(sample_idea_set)

        assert captured[0] == custom_formatter


# ── 우연 도메인 풀 교체 ───────────────────────────────────

class TestSerendipityDomainOverride:
    def test_custom_domains_pool(self):
        """서비스별 도메인 풀로 교체 가능."""
        custom_domains = ["해킹", "양자역학", "마케팅"]
        config = EngineConfig(serendipity_domains=custom_domains)
        mock_llm = MockLLMClient(json.dumps([
            {"content": "아이디어", "rationale": "이유", "source_domains": ["해킹"], "connections": []}
        ]))
        gen = SerendipityGenerator(client=mock_llm, config=config)
        bundle = InputBundle(problem=CreativityProblem(
            goal="목표", divergence_n=5, serendipity=1.0
        ))
        gen.run(bundle)

        user_prompt = mock_llm.calls[0][1]
        any_custom = any(d in user_prompt for d in custom_domains)
        assert any_custom
        any_default = any(d in user_prompt for d in DEFAULT_SERENDIPITY_DOMAINS
                         if d not in custom_domains)
        assert not any_default


# ── extra_generators ─────────────────────────────────────

class TestExtraGenerators:
    def test_extra_generator_called(self):
        """extra_generators의 run()이 파이프라인에서 호출되어야 함."""
        extra_ideas = [
            Idea(content="외부 아이디어", rationale="외부", source_domains=["외부"], connections=[])
        ]

        class ExtraGen:
            def run(self, bundle):
                return extra_ideas

        mock_llm = MockLLMClient("[]")
        config = EngineConfig(llm_client=mock_llm, extra_generators=[ExtraGen()])
        engine = ConnectionEngine(config=config)
        bundle = InputBundle(problem=CreativityProblem(goal="목표", divergence_n=1, top_k=1))
        idea_set = engine.run(bundle)

        contents = [i.content for i in idea_set.all_ideas]
        assert "외부 아이디어" in contents

    def test_extra_generator_error_does_not_crash(self):
        """extra_generator 오류 시 파이프라인 중단 없이 계속 진행."""
        class BrokenGen:
            def run(self, bundle):
                raise RuntimeError("broken")

        mock_llm = MockLLMClient(json.dumps([
            {"content": "정상 아이디어", "rationale": "이유", "source_domains": ["A"], "connections": []}
        ]))
        config = EngineConfig(llm_client=mock_llm, extra_generators=[BrokenGen()])
        engine = ConnectionEngine(config=config)
        bundle = InputBundle(problem=CreativityProblem(goal="목표", divergence_n=1, top_k=1))
        idea_set = engine.run(bundle)
        # 정상 아이디어는 포함되어야 함
        assert len(idea_set.all_ideas) >= 1


# ── BaseLLMClient 계약 ───────────────────────────────────

class TestBaseLLMClientContract:
    def test_cannot_instantiate_abstract(self):
        """BaseLLMClient는 직접 인스턴스화 불가."""
        with pytest.raises(TypeError):
            BaseLLMClient()

    def test_mock_implements_contract(self):
        """MockLLMClient가 BaseLLMClient를 올바르게 구현."""
        client = MockLLMClient("응답")
        assert isinstance(client, BaseLLMClient)
        result = client.call("sys", "user")
        assert result == "응답"
