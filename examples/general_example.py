"""
원격 근무자 집중력 문제 — GeneralAdapter 예시

실행:
    python examples/general_example.py
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from creativity_engine import CreativityEngine, GeneralAdapter


def main():
    engine = CreativityEngine(adapter=GeneralAdapter())

    # ── 빠른 테스트용 (divergence_n=3) ──
    print("=" * 60)
    print("Creativity Engine — General Example")
    print("=" * 60)

    result = engine.run(
        goal="원격 근무자의 집중력 저하 문제를 해결하고 싶다",
        constraints=["예산 50만원 이하", "앱 개발 불가"],
        context={"team_size": 5, "industry": "스타트업"},
        divergence_n=5,
        top_k=3,
    )

    print("\n[솔루션]")
    print(result["solution"])

    print("\n[상위 아이디어]")
    for i, idea in enumerate(result["top_ideas"], 1):
        print(f"  {i}. {idea['content']}")
        print(f"     점수: {idea['score']:.2f} | 출처 도메인: {idea['from_domains']}")

    print("\n[자기평가]")
    print(result["reflection"] or "반성 루프 미실행")

    print(f"\n[신뢰도] {result['confidence']:.2f}")

    # ── 디버그: run_raw로 전체 IdeaSet 확인 ──
    print("\n" + "=" * 60)
    print("DEBUG: 전체 아이디어 목록 (run_raw)")
    print("=" * 60)

    solution = engine.run_raw(
        "팀 내 커뮤니케이션 과부하 문제",
        divergence_n=3,
        top_k=1,
        max_reflection_rounds=0,
    )

    print(f"\n총 생성 아이디어: {len(solution.idea_set.all_ideas)}개")
    for idea in solution.idea_set.all_ideas:
        print(f"  [{idea.final_score:.2f}] {idea.content[:80]}...")
        print(f"         출처: {idea.source_domains}")

    print(f"\n선택된 아이디어: {solution.selected_idea.content[:100]}")
    print(f"신뢰도: {solution.confidence:.2f}")


if __name__ == "__main__":
    main()
