"""connection_engine 단위 테스트 — MockLLMClient 주입."""
import json
from unittest.mock import patch

import pytest

from creativity_engine.config import EngineConfig
from creativity_engine.core.connection_engine import (
    ConstraintRelaxer,
    ConvergenceRanker,
    CrossDomainLinker,
    DivergenceGenerator,
    NoveltyScorer,
    ConnectionEngine,
    _calculate_final_score,
    _diverse_top_k,
    _extract_json,
    _parse_ideas_json,
)
from creativity_engine.core.models import Idea, IdeaSet, InputBundle


# ── Utility 함수 테스트 ──────────────────────────────────

class TestExtractJson:
    def test_plain_json(self):
        result = _extract_json('[{"content": "x"}]')
        assert result == '[{"content": "x"}]'

    def test_strips_markdown_fence(self):
        text = '```json\n[{"content": "x"}]\n```'
        result = _extract_json(text)
        assert result == '[{"content": "x"}]'

    def test_strips_generic_fence(self):
        text = '```\n[{"content": "x"}]\n```'
        result = _extract_json(text)
        assert result == '[{"content": "x"}]'


class TestParseIdeasJson:
    def test_valid_json(self):
        text = '[{"content": "아이디어", "rationale": "이유", "source_domains": ["심리학"], "connections": []}]'
        result = _parse_ideas_json(text)
        assert len(result) == 1
        assert result[0]["content"] == "아이디어"

    def test_invalid_json_returns_empty(self):
        result = _parse_ideas_json("invalid json {{{")
        assert result == []

    def test_json_in_fence(self):
        text = '```json\n[{"content": "x", "rationale": "", "source_domains": [], "connections": []}]\n```'
        result = _parse_ideas_json(text)
        assert len(result) == 1


class TestCalculateFinalScore:
    def test_default_weights(self):
        idea = Idea(content="x", novelty_score=1.0, feasibility_score=0.0)
        score = _calculate_final_score(idea)
        assert score == pytest.approx(0.6)

    def test_custom_weights(self):
        idea = Idea(content="x", novelty_score=0.5, feasibility_score=0.5)
        score = _calculate_final_score(idea, {"novelty": 0.5, "feasibility": 0.5})
        assert score == pytest.approx(0.5)

    def test_score_clamped_to_one(self):
        idea = Idea(content="x", novelty_score=1.0, feasibility_score=1.0)
        score = _calculate_final_score(idea)
        assert score <= 1.0


class TestDiverseTopK:
    def test_returns_k_items(self, sample_ideas):
        result = _diverse_top_k(sample_ideas, k=2)
        assert len(result) == 2

    def test_empty_input(self):
        result = _diverse_top_k([], k=3)
        assert result == []

    def test_prefers_diverse_domains(self):
        ideas = [
            Idea(content="A", source_domains=["심리학"], final_score=0.9),
            Idea(content="B", source_domains=["심리학"], final_score=0.8),
            Idea(content="C", source_domains=["게임디자인"], final_score=0.7),
        ]
        result = _diverse_top_k(ideas, k=2)
        contents = [i.content for i in result]
        assert "A" in contents
        assert "C" in contents

    def test_fallback_when_not_diverse_enough(self):
        ideas = [
            Idea(content="A", source_domains=["심리학"], final_score=0.9),
            Idea(content="B", source_domains=["심리학"], final_score=0.8),
        ]
        result = _diverse_top_k(ideas, k=2)
        assert len(result) == 2


# ── Component 테스트 (MockLLMClient 주입) ──────────────

MOCK_IDEAS_JSON = json.dumps([
    {"content": "아이디어1", "rationale": "이유1", "source_domains": ["심리학"], "connections": ["집중력"]},
    {"content": "아이디어2", "rationale": "이유2", "source_domains": ["게임"], "connections": ["보상"]},
])


class TestDivergenceGenerator:
    def test_run_returns_ideas(self, sample_bundle, mock_llm):
        mock_llm.set_return(MOCK_IDEAS_JSON)
        gen = DivergenceGenerator(client=mock_llm)
        ideas = gen.run(sample_bundle)
        assert len(ideas) == 2
        assert ideas[0].content == "아이디어1"
        assert ideas[0].source_domains == ["심리학"]

    def test_run_handles_json_parse_error(self, sample_bundle, mock_llm):
        mock_llm.set_return("not json")
        gen = DivergenceGenerator(client=mock_llm)
        ideas = gen.run(sample_bundle)
        assert ideas == []


class TestCrossDomainLinker:
    def test_run_returns_ideas(self, sample_bundle, sample_ideas, mock_llm):
        mock_llm.set_return(MOCK_IDEAS_JSON)
        linker = CrossDomainLinker(client=mock_llm)
        ideas = linker.run(sample_bundle, sample_ideas)
        assert len(ideas) >= 1

    def test_run_with_empty_existing(self, sample_bundle, mock_llm):
        mock_llm.set_return(MOCK_IDEAS_JSON)
        linker = CrossDomainLinker(client=mock_llm)
        ideas = linker.run(sample_bundle, [])
        assert isinstance(ideas, list)


class TestConstraintRelaxer:
    def test_run_returns_ideas(self, sample_bundle, mock_llm):
        mock_llm.set_return(MOCK_IDEAS_JSON)
        relaxer = ConstraintRelaxer(client=mock_llm)
        ideas = relaxer.run(sample_bundle)
        assert isinstance(ideas, list)

    def test_run_with_no_constraints(self, basic_problem):
        no_constraint_bundle = InputBundle(
            problem=basic_problem.model_copy(update={"constraints": []}),
        )
        relaxer = ConstraintRelaxer()
        ideas = relaxer.run(no_constraint_bundle)
        assert ideas == []


class TestNoveltyScorer:
    def test_scores_assigned(self, sample_ideas, basic_problem):
        mock_scores = json.dumps([
            {"id": idea.id, "novelty_score": 0.7, "feasibility_score": 0.6}
            for idea in sample_ideas
        ])
        from tests.conftest import MockLLMClient
        mock_llm = MockLLMClient(mock_scores)
        scorer = NoveltyScorer(client=mock_llm)
        scored = scorer.run(sample_ideas, basic_problem.goal, basic_problem.constraints)

        for idea in scored:
            assert idea.novelty_score == pytest.approx(0.7)
            assert idea.feasibility_score == pytest.approx(0.6)
            assert idea.final_score > 0.0

    def test_empty_ideas(self, basic_problem):
        scorer = NoveltyScorer()
        result = scorer.run([], basic_problem.goal, basic_problem.constraints)
        assert result == []


class TestConvergenceRanker:
    def test_returns_top_k(self, sample_ideas):
        ranker = ConvergenceRanker(use_diverse_ranking=False)
        result = ranker.run(sample_ideas, top_k=2)
        assert len(result) == 2

    def test_sorted_by_score(self, sample_ideas):
        for i, idea in enumerate(sample_ideas):
            idea.final_score = float(i) / 10
        ranker = ConvergenceRanker(use_diverse_ranking=False)
        result = ranker.run(sample_ideas, top_k=2)
        assert result[0].final_score >= result[1].final_score

    def test_diverse_ranking(self, sample_ideas):
        ranker = ConvergenceRanker(use_diverse_ranking=True)
        result = ranker.run(sample_ideas, top_k=2)
        assert len(result) <= 2

    def test_empty_input(self):
        ranker = ConvergenceRanker()
        result = ranker.run([], top_k=3)
        assert result == []


class TestConnectionEngine:
    def test_run_returns_idea_set(self, sample_bundle):
        mock_ideas_json = json.dumps([
            {"content": f"아이디어{i}", "rationale": "이유", "source_domains": [f"도메인{i}"], "connections": []}
            for i in range(3)
        ])
        from tests.conftest import MockLLMClient
        mock_llm = MockLLMClient(mock_ideas_json)
        config = EngineConfig(llm_client=mock_llm)
        engine = ConnectionEngine(config=config)
        idea_set = engine.run(sample_bundle)

        assert isinstance(idea_set, IdeaSet)
        assert len(idea_set.all_ideas) > 0
        assert isinstance(idea_set.top_ideas, list)
