"""adapters 단위 테스트 — Claude API 호출 없음."""
import pytest

from creativity_engine.core.models import CreativityProblem
from creativity_engine.adapters import (
    GeneralAdapter,
    LegalAdapter,
    MarketingAdapter,
    SoftwareAdapter,
    ADAPTER_REGISTRY,
    get_adapter,
    get_adapter_or_default,
)


class TestGeneralAdapter:
    def setup_method(self):
        self.adapter = GeneralAdapter()

    def test_format_str_input(self):
        p = self.adapter.format_problem("테스트 목표")
        assert p.goal == "테스트 목표"
        assert p.constraints == []
        assert p.context == {}

    def test_format_dict_input(self):
        p = self.adapter.format_problem({
            "goal": "목표",
            "constraints": ["제약1"],
            "context": {"key": "val"},
            "divergence_n": 5,
            "top_k": 2,
        })
        assert p.goal == "목표"
        assert p.constraints == ["제약1"]
        assert p.divergence_n == 5
        assert p.top_k == 2

    def test_format_dict_with_problem_key(self):
        p = self.adapter.format_problem({"problem": "문제 설명"})
        assert p.goal == "문제 설명"

    def test_render_solution(self, sample_idea_set, sample_idea):
        from creativity_engine.core.models import Solution
        sol = Solution(
            problem=sample_idea_set.problem,
            idea_set=sample_idea_set,
            selected_idea=sample_idea,
            solution_text="솔루션",
            confidence=0.75,
        )
        result = self.adapter.render_solution(sol)
        assert "solution" in result
        assert "top_ideas" in result
        assert "confidence" in result
        assert result["confidence"] == 0.75
        assert isinstance(result["top_ideas"], list)

    def test_validate_returns_empty(self):
        p = CreativityProblem(goal="x")
        assert self.adapter.validate_problem(p) == []

    def test_get_domain_name(self):
        assert self.adapter.get_domain_name() == "GeneralAdapter"


class TestLegalAdapter:
    def setup_method(self):
        self.adapter = LegalAdapter()

    def test_format_str(self):
        p = self.adapter.format_problem("법률 문제")
        assert p.domain_hint == "legal"
        assert p.goal == "법률 문제"

    def test_format_dict_full(self):
        p = self.adapter.format_problem({
            "case_type": "계약 분쟁",
            "facts": "A사가 납품 기한 초과",
            "client_position": "A사",
            "jurisdiction": "대한민국",
            "desired_outcome": "위약금 감액",
            "constraints": ["소송 비용 최소화"],
        })
        assert p.domain_hint == "legal"
        assert p.divergence_n == 8
        assert "관할: 대한민국 법률 적용" in p.constraints
        assert "사건 유형: 계약 분쟁" in p.constraints
        assert "소송 비용 최소화" in p.constraints
        assert "A사가 납품 기한 초과" in p.goal

    def test_validate_warns_without_jurisdiction(self):
        p = CreativityProblem(goal="법률 문제", constraints=[])
        warnings = self.adapter.validate_problem(p)
        assert len(warnings) == 1
        assert "관할" in warnings[0]

    def test_validate_passes_with_jurisdiction(self):
        p = CreativityProblem(goal="x", constraints=["관할: 대한민국"])
        warnings = self.adapter.validate_problem(p)
        assert warnings == []

    def test_render_has_disclaimer(self, sample_idea_set, sample_idea):
        from creativity_engine.core.models import Solution
        sol = Solution(
            problem=sample_idea_set.problem,
            idea_set=sample_idea_set,
            selected_idea=sample_idea,
            solution_text="전략",
            confidence=0.7,
        )
        result = self.adapter.render_solution(sol)
        assert "disclaimer" in result
        assert "legal_strategies" in result
        assert "risk_assessment" in result


class TestMarketingAdapter:
    def setup_method(self):
        self.adapter = MarketingAdapter()

    def test_format_str(self):
        p = self.adapter.format_problem("마케팅 문제")
        assert p.domain_hint == "marketing"

    def test_format_dict(self):
        p = self.adapter.format_problem({
            "product": "SaaS 툴",
            "target_audience": "스타트업 CTO",
            "challenge": "인지도 낮음",
            "budget": "월 300만원",
            "channels_available": ["LinkedIn", "콘텐츠"],
            "kpi": "500명 가입",
        })
        assert p.divergence_n == 12
        assert p.domain_hint == "marketing"
        assert "예산: 월 300만원" in p.constraints
        assert "사용 가능 채널: LinkedIn, 콘텐츠" in p.constraints
        assert "SaaS 툴" in p.goal

    def test_render_structure(self, sample_idea_set, sample_idea):
        from creativity_engine.core.models import Solution
        sol = Solution(
            problem=sample_idea_set.problem,
            idea_set=sample_idea_set,
            selected_idea=sample_idea,
            solution_text="캠페인",
            confidence=0.8,
        )
        result = self.adapter.render_solution(sol)
        assert "campaign_concepts" in result
        assert "execution_plan" in result
        assert "inspiration_sources" in result
        for concept in result["campaign_concepts"]:
            assert "rank" in concept
            assert "concept_name" in concept


class TestSoftwareAdapter:
    def setup_method(self):
        self.adapter = SoftwareAdapter()

    def test_format_str(self):
        p = self.adapter.format_problem("시스템 설계 문제")
        assert p.domain_hint == "software"

    def test_format_dict(self):
        p = self.adapter.format_problem({
            "problem": "데이터 일관성",
            "current_stack": ["Python", "FastAPI"],
            "scale": "DAU 10만",
            "nfr": ["99.9% 가용성"],
            "team_size": 4,
            "constraints": ["기존 DB 교체 불가"],
        })
        assert p.domain_hint == "software"
        assert p.max_reflection_rounds == 2
        assert p.divergence_n == 8
        assert "팀 규모: 4명" in p.constraints
        assert "기존 DB 교체 불가" in p.constraints

    def test_render_structure(self, sample_idea_set, sample_idea):
        from creativity_engine.core.models import Solution, Action, ActionType
        sol = Solution(
            problem=sample_idea_set.problem,
            idea_set=sample_idea_set,
            selected_idea=sample_idea,
            solution_text="설계안",
            confidence=0.85,
            actions=[Action(type=ActionType.TEXT, payload={}, result="힌트1")],
        )
        result = self.adapter.render_solution(sol)
        assert "design_options" in result
        assert "recommended_design" in result
        assert "implementation_hints" in result
        assert "힌트1" in result["implementation_hints"]
        for opt in result["design_options"]:
            assert "complexity" in opt
            # complexity = 1 - feasibility_score
            assert 0.0 <= opt["complexity"] <= 1.0


class TestAdapterRegistry:
    def test_all_domains_registered(self):
        assert set(ADAPTER_REGISTRY.keys()) == {"general", "legal", "marketing", "software"}

    def test_get_adapter_returns_correct_type(self):
        assert isinstance(get_adapter("general"), GeneralAdapter)
        assert isinstance(get_adapter("legal"), LegalAdapter)
        assert isinstance(get_adapter("marketing"), MarketingAdapter)
        assert isinstance(get_adapter("software"), SoftwareAdapter)

    def test_get_adapter_raises_on_unknown(self):
        with pytest.raises(ValueError, match="Unknown domain"):
            get_adapter("unknown")

    def test_get_adapter_or_default_fallback(self):
        adapter = get_adapter_or_default("nonexistent")
        assert isinstance(adapter, GeneralAdapter)

    def test_get_adapter_or_default_known(self):
        adapter = get_adapter_or_default("legal")
        assert isinstance(adapter, LegalAdapter)
