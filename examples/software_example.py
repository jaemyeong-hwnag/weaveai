"""
마이크로서비스 데이터 일관성 — SoftwareAdapter 예시

실행:
    python examples/software_example.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from creativity_engine import CreativityEngine, SoftwareAdapter


def main():
    engine = CreativityEngine(adapter=SoftwareAdapter())

    print("=" * 60)
    print("Creativity Engine — Software Design Example")
    print("=" * 60)

    result = engine.run({
        "problem": "마이크로서비스 간 데이터 일관성 보장이 어렵다",
        "current_stack": ["Python", "FastAPI", "PostgreSQL", "RabbitMQ"],
        "scale": "DAU 10만",
        "nfr": ["99.9% 가용성", "응답시간 200ms 이하"],
        "team_size": 4,
        "constraints": ["기존 DB 교체 불가", "6주 내 구현"],
    })

    print("\n[설계 옵션]")
    for option in result["design_options"]:
        print(f"\n  패턴: {option['pattern']}")
        print(f"  근거: {option['rationale']}")
        print(f"  영감: {option['inspired_by']}")
        print(f"  복잡도: {option['complexity']:.2f} | 참신성: {option['novelty']:.2f}")
        if option["key_concepts"]:
            print(f"  핵심 개념: {', '.join(option['key_concepts'])}")

    print("\n[권장 설계]")
    print(result["recommended_design"])

    print("\n[트레이드오프]")
    print(result["trade_offs"] or "반성 루프 미실행")

    print("\n[구현 힌트]")
    hints = result["implementation_hints"]
    if hints:
        for hint in hints:
            print(f"  - {hint}")
    else:
        print("  (없음)")

    print(f"\n[신뢰도] {result['confidence']:.2f}")


if __name__ == "__main__":
    main()
