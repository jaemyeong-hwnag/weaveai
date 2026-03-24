"""
계약 분쟁 법률 전략 — LegalAdapter 예시

실행:
    python examples/legal_example.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from creativity_engine import CreativityEngine, LegalAdapter


def main():
    engine = CreativityEngine(adapter=LegalAdapter())

    print("=" * 60)
    print("Creativity Engine — Legal Example")
    print("=" * 60)

    result = engine.run({
        "case_type": "계약 분쟁",
        "facts": "A사가 납품 기한을 3일 초과했고 B사는 전액 위약금을 요구 중",
        "client_position": "A사 (납품사)",
        "jurisdiction": "대한민국",
        "desired_outcome": "위약금 감액 또는 면제",
        "constraints": ["소송 비용 최소화", "거래 관계 유지 희망"],
    })

    print("\n[법률 전략]")
    for i, strategy in enumerate(result["legal_strategies"], 1):
        print(f"\n  전략 {i}: {strategy['strategy']}")
        print(f"  법적 근거: {strategy['legal_basis']}")
        print(f"  참신성: {strategy['novelty']:.2f} | 실현가능성: {strategy['feasibility']:.2f}")
        print(f"  크로스도메인 영감: {strategy['cross_domain_inspiration']}")

    print("\n[권고 접근법]")
    print(result["recommended_approach"])

    print("\n[리스크 평가]")
    print(result["risk_assessment"])

    print(f"\n[신뢰도] {result['confidence']:.2f}")
    print(f"\n[면책 고지] {result['disclaimer']}")


if __name__ == "__main__":
    main()
