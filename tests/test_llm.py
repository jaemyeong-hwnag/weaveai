"""LLM 추상화 레이어 테스트."""
from unittest.mock import MagicMock, patch

import pytest

from creativity_engine.llm.base import BaseLLMClient
from creativity_engine.llm.claude import ClaudeClient


class TestClaudeClient:
    def _make_response(self, text: str):
        mock = MagicMock()
        mock.content = [MagicMock(text=text)]
        return mock

    def test_call_returns_text(self):
        with patch("creativity_engine.llm.claude.anthropic.Anthropic") as mock_anthropic:
            instance = mock_anthropic.return_value
            instance.messages.create.return_value = self._make_response("응답 텍스트")
            client = ClaudeClient(api_key="test-key")
            result = client.call("시스템", "사용자")
        assert result == "응답 텍스트"

    def test_call_uses_model(self):
        with patch("creativity_engine.llm.claude.anthropic.Anthropic") as mock_anthropic:
            instance = mock_anthropic.return_value
            instance.messages.create.return_value = self._make_response("응답")
            client = ClaudeClient(api_key="test", model="claude-haiku-4-5-20251001")
            client.call("sys", "user")
            call_kwargs = instance.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"

    def test_call_uses_max_tokens(self):
        with patch("creativity_engine.llm.claude.anthropic.Anthropic") as mock_anthropic:
            instance = mock_anthropic.return_value
            instance.messages.create.return_value = self._make_response("응답")
            client = ClaudeClient(api_key="test")
            client.call("sys", "user", max_tokens=256)
            call_kwargs = instance.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 256

    def test_call_retries_on_error(self):
        with patch("creativity_engine.llm.claude.anthropic.Anthropic") as mock_anthropic:
            instance = mock_anthropic.return_value
            # 첫 번째 실패, 두 번째 성공
            instance.messages.create.side_effect = [
                Exception("일시적 오류"),
                self._make_response("재시도 성공"),
            ]
            client = ClaudeClient(api_key="test", retries=1)
            result = client.call("sys", "user")
        assert result == "재시도 성공"
        assert instance.messages.create.call_count == 2

    def test_call_raises_after_max_retries(self):
        with patch("creativity_engine.llm.claude.anthropic.Anthropic") as mock_anthropic:
            instance = mock_anthropic.return_value
            instance.messages.create.side_effect = Exception("지속 오류")
            client = ClaudeClient(api_key="test", retries=1)
            with pytest.raises(Exception, match="지속 오류"):
                client.call("sys", "user")
        assert instance.messages.create.call_count == 2

    def test_is_base_llm_client(self):
        with patch("creativity_engine.llm.claude.anthropic.Anthropic"):
            client = ClaudeClient(api_key="test")
        assert isinstance(client, BaseLLMClient)
