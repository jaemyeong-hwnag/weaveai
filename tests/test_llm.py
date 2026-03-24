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


class TestOpenAIClient:
    def _make_response(self, text: str):
        mock = MagicMock()
        mock.choices = [MagicMock()]
        mock.choices[0].message.content = text
        return mock

    def _make_client(self, return_value="응답"):
        import sys
        openai_mock = MagicMock()
        openai_mock.OpenAI.return_value.chat.completions.create.return_value = (
            self._make_response(return_value)
        )
        with patch.dict(sys.modules, {"openai": openai_mock}):
            from creativity_engine.llm.openai import OpenAIClient
            client = OpenAIClient(api_key="test-key")
        # keep reference to mock for assertions
        client._raw_mock = openai_mock.OpenAI.return_value
        return client

    def test_call_returns_text(self):
        client = self._make_client("GPT 응답")
        client._client = client._raw_mock
        result = client.call("시스템", "사용자")
        assert result == "GPT 응답"

    def test_call_sends_system_and_user(self):
        client = self._make_client()
        client._client = client._raw_mock
        client.call("sys prompt", "user prompt")
        kwargs = client._raw_mock.chat.completions.create.call_args[1]
        messages = kwargs["messages"]
        assert messages[0] == {"role": "system", "content": "sys prompt"}
        assert messages[1] == {"role": "user", "content": "user prompt"}

    def test_call_retries_on_error(self):
        import sys
        openai_mock = MagicMock()
        instance = openai_mock.OpenAI.return_value
        instance.chat.completions.create.side_effect = [
            Exception("일시적 오류"),
            self._make_response("재시도 성공"),
        ]
        with patch.dict(sys.modules, {"openai": openai_mock}):
            from creativity_engine.llm.openai import OpenAIClient
            client = OpenAIClient(api_key="test", retries=1)
        client._client = instance
        result = client.call("sys", "user")
        assert result == "재시도 성공"
        assert instance.chat.completions.create.call_count == 2

    def test_import_error_without_package(self):
        import sys
        with patch.dict(sys.modules, {"openai": None}):
            import importlib
            import creativity_engine.llm.openai as mod
            importlib.reload(mod)
            with pytest.raises(ImportError, match="openai"):
                mod.OpenAIClient(api_key="test")

    def test_is_base_llm_client(self):
        import sys
        openai_mock = MagicMock()
        openai_mock.OpenAI.return_value.chat.completions.create.return_value = (
            self._make_response("ok")
        )
        with patch.dict(sys.modules, {"openai": openai_mock}):
            from creativity_engine.llm.openai import OpenAIClient
            client = OpenAIClient(api_key="test")
        assert isinstance(client, BaseLLMClient)


class TestGeminiClient:
    def _make_response(self, text: str):
        mock = MagicMock()
        mock.text = text
        return mock

    def _patch_genai(self, return_value="Gemini 응답"):
        """Returns (patch_dict_context, client_instance_mock)."""
        import sys
        genai_mock = MagicMock()
        genai_types_mock = MagicMock()
        client_instance = genai_mock.Client.return_value
        client_instance.models.generate_content.return_value = self._make_response(return_value)
        google_mock = MagicMock()
        google_mock.genai = genai_mock
        modules = {
            "google": google_mock,
            "google.genai": genai_mock,
            "google.genai.types": genai_types_mock,
        }
        return modules, client_instance

    def test_call_returns_text(self):
        import sys
        modules, instance = self._patch_genai("Gemini 응답")
        with patch.dict(sys.modules, modules):
            import importlib
            import creativity_engine.llm.gemini as mod
            importlib.reload(mod)
            client = mod.GeminiClient(api_key="test-key")
        client._client = instance
        result = client.call("시스템", "사용자")
        assert result == "Gemini 응답"

    def test_call_combines_system_and_user(self):
        import sys
        modules, instance = self._patch_genai()
        with patch.dict(sys.modules, modules):
            import importlib
            import creativity_engine.llm.gemini as mod
            importlib.reload(mod)
            client = mod.GeminiClient(api_key="test-key")
        client._client = instance
        client.call("sys", "usr")
        kwargs = instance.models.generate_content.call_args[1]
        contents = kwargs["contents"]
        assert "sys" in contents and "usr" in contents

    def test_call_retries_on_error(self):
        import sys
        modules, instance = self._patch_genai()
        instance.models.generate_content.side_effect = [
            Exception("일시적 오류"),
            self._make_response("재시도 성공"),
        ]
        with patch.dict(sys.modules, modules):
            import importlib
            import creativity_engine.llm.gemini as mod
            importlib.reload(mod)
            client = mod.GeminiClient(api_key="test", retries=1)
        client._client = instance
        result = client.call("sys", "user")
        assert result == "재시도 성공"

    def test_import_error_without_package(self):
        import sys
        with patch.dict(sys.modules, {"google.genai": None}):
            import importlib
            import creativity_engine.llm.gemini as mod
            importlib.reload(mod)
            with pytest.raises(ImportError, match="google-genai"):
                mod.GeminiClient(api_key="test")

    def test_is_base_llm_client(self):
        import sys
        modules, _ = self._patch_genai()
        with patch.dict(sys.modules, modules):
            import importlib
            import creativity_engine.llm.gemini as mod
            importlib.reload(mod)
            client = mod.GeminiClient(api_key="test")
        assert isinstance(client, BaseLLMClient)


class TestOllamaClient:
    def _make_response(self, text: str):
        return {"message": {"content": text}}

    def _make_client(self, return_value="Ollama 응답"):
        import sys
        ollama_mock = MagicMock()
        ollama_mock.Client.return_value.chat.return_value = self._make_response(return_value)
        with patch.dict(sys.modules, {"ollama": ollama_mock}):
            from creativity_engine.llm.ollama import OllamaClient
            client = OllamaClient(model="llama3.2")
        client._raw_instance = ollama_mock.Client.return_value
        return client

    def test_call_returns_text(self):
        client = self._make_client("Ollama 응답")
        client._client = client._raw_instance
        result = client.call("시스템", "사용자")
        assert result == "Ollama 응답"

    def test_call_sends_model_name(self):
        client = self._make_client()
        client._client = client._raw_instance
        client.call("sys", "user")
        kwargs = client._raw_instance.chat.call_args[1]
        assert kwargs["model"] == "llama3.2"

    def test_call_sends_num_predict(self):
        client = self._make_client()
        client._client = client._raw_instance
        client.call("sys", "user", max_tokens=512)
        kwargs = client._raw_instance.chat.call_args[1]
        assert kwargs["options"]["num_predict"] == 512

    def test_call_retries_on_error(self):
        import sys
        ollama_mock = MagicMock()
        instance = ollama_mock.Client.return_value
        instance.chat.side_effect = [
            Exception("연결 오류"),
            self._make_response("재시도 성공"),
        ]
        with patch.dict(sys.modules, {"ollama": ollama_mock}):
            from creativity_engine.llm.ollama import OllamaClient
            client = OllamaClient(retries=1)
        client._client = instance
        result = client.call("sys", "user")
        assert result == "재시도 성공"

    def test_import_error_without_package(self):
        import sys
        with patch.dict(sys.modules, {"ollama": None}):
            import importlib
            import creativity_engine.llm.ollama as mod
            importlib.reload(mod)
            with pytest.raises(ImportError, match="ollama"):
                mod.OllamaClient()

    def test_is_base_llm_client(self):
        import sys
        ollama_mock = MagicMock()
        with patch.dict(sys.modules, {"ollama": ollama_mock}):
            from creativity_engine.llm.ollama import OllamaClient
            client = OllamaClient()
        assert isinstance(client, BaseLLMClient)
