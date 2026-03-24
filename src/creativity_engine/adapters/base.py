from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..core.models import CreativityProblem, Solution


class DomainAdapter(ABC):

    @abstractmethod
    def format_problem(self, raw: dict | str) -> CreativityProblem:
        """
        도메인 입력 → CreativityProblem 변환.

        raw가 str이면 goal로 처리하고 나머지는 기본값.
        raw가 dict이면 도메인별 키를 파싱해 매핑.

        이 메서드 안에서만 도메인 용어가 등장해야 합니다.
        """
        ...

    @abstractmethod
    def render_solution(self, solution: Solution) -> Any:
        """
        Solution → 도메인 출력 포맷 변환.

        반환 타입 제한 없음 (dict, str, 도메인 객체 등).
        이 메서드 안에서만 도메인 출력 로직이 존재해야 합니다.
        """
        ...

    def validate_problem(self, problem: CreativityProblem) -> list[str]:
        """
        (선택 구현) 도메인 특화 입력 유효성 검사.
        반환: 경고 메시지 목록 (빈 리스트면 이상 없음).
        """
        return []

    def get_domain_name(self) -> str:
        """어댑터 이름. 로깅·디버깅용."""
        return self.__class__.__name__
