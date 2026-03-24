"""core/models.py 단위 테스트."""
import pytest
from pydantic import ValidationError

from creativity_engine.core.models import (
    Action,
    ActionType,
    CreativityProblem,
    Document,
    Idea,
    IdeaSet,
    InputBundle,
    Signal,
    Solution,
)


class TestCreativityProblem:
    def test_defaults(self):
        p = CreativityProblem(goal="테스트")
        assert p.divergence_n == 10
        assert p.top_k == 3
        assert p.max_reflection_rounds == 2
        assert p.constraints == []
        assert p.context == {}
        assert p.domain_hint is None

    def test_custom_values(self):
        p = CreativityProblem(
            goal="목표",
            constraints=["제약1"],
            divergence_n=5,
            top_k=2,
            domain_hint="legal",
        )
        assert p.constraints == ["제약1"]
        assert p.divergence_n == 5
        assert p.domain_hint == "legal"

    def test_mutable_defaults_are_independent(self):
        p1 = CreativityProblem(goal="A")
        p2 = CreativityProblem(goal="B")
        p1.constraints.append("x")
        assert p2.constraints == []  # 공유되지 않아야 함


class TestDocument:
    def test_relevance_bounds(self):
        with pytest.raises(ValidationError):
            Document(content="x", source="web", relevance=1.5)
        with pytest.raises(ValidationError):
            Document(content="x", source="web", relevance=-0.1)

    def test_valid_document(self):
        doc = Document(content="내용", source="rag", relevance=0.7)
        assert doc.relevance == 0.7
        assert doc.metadata == {}


class TestSignal:
    def test_strength_bounds(self):
        with pytest.raises(ValidationError):
            Signal(content="x", signal_type="trend", strength=2.0)

    def test_valid_signal(self):
        s = Signal(content="신호", signal_type="edge_case", strength=0.3)
        assert s.signal_type == "edge_case"


class TestIdea:
    def test_unique_ids(self):
        i1 = Idea(content="A")
        i2 = Idea(content="B")
        assert i1.id != i2.id

    def test_score_bounds(self):
        with pytest.raises(ValidationError):
            Idea(content="x", novelty_score=1.5)
        with pytest.raises(ValidationError):
            Idea(content="x", feasibility_score=-0.1)

    def test_defaults(self):
        idea = Idea(content="테스트 아이디어")
        assert idea.novelty_score == 0.0
        assert idea.source_domains == []
        assert idea.connections == []


class TestIdeaSet:
    def test_creation(self, basic_problem, sample_ideas):
        idea_set = IdeaSet(
            problem=basic_problem,
            all_ideas=sample_ideas,
            top_ideas=sample_ideas[:2],
        )
        assert len(idea_set.all_ideas) == 3
        assert len(idea_set.top_ideas) == 2

    def test_empty_defaults(self, basic_problem):
        idea_set = IdeaSet(problem=basic_problem)
        assert idea_set.all_ideas == []
        assert idea_set.top_ideas == []
        assert idea_set.divergence_log == []


class TestInputBundle:
    def test_creation(self, basic_problem):
        bundle = InputBundle(problem=basic_problem)
        assert bundle.knowledge == []
        assert bundle.signals == []
        assert bundle.context_summary == ""

    def test_with_data(self, sample_bundle):
        assert len(sample_bundle.knowledge) == 1
        assert len(sample_bundle.signals) == 1
        assert "목표" in sample_bundle.context_summary


class TestAction:
    def test_action_types(self):
        for t in ActionType:
            a = Action(type=t)
            assert a.type == t

    def test_result_any_type(self):
        a = Action(type=ActionType.TEXT, payload={"text": "hello"}, result={"key": "value"})
        assert a.result == {"key": "value"}

    def test_result_none_default(self):
        a = Action(type=ActionType.TEXT)
        assert a.result is None


class TestSolution:
    def test_confidence_required(self, basic_problem, sample_idea_set, sample_idea):
        with pytest.raises(ValidationError):
            Solution(
                problem=basic_problem,
                idea_set=sample_idea_set,
                selected_idea=sample_idea,
                solution_text="솔루션",
                # confidence 누락 → ValidationError
            )

    def test_confidence_bounds(self, basic_problem, sample_idea_set, sample_idea):
        with pytest.raises(ValidationError):
            Solution(
                problem=basic_problem,
                idea_set=sample_idea_set,
                selected_idea=sample_idea,
                solution_text="솔루션",
                confidence=1.5,
            )

    def test_valid_solution(self, basic_problem, sample_idea_set, sample_idea):
        sol = Solution(
            problem=basic_problem,
            idea_set=sample_idea_set,
            selected_idea=sample_idea,
            solution_text="솔루션 텍스트",
            confidence=0.8,
        )
        assert sol.confidence == 0.8
        assert sol.reflection is None
        assert sol.reflection_rounds == 0
        assert sol.actions == []
