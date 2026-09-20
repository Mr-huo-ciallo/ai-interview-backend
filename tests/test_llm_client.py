import pytest

import llm_client


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self.content}}]}


class FakeClient:
    def __init__(self, captured, content):
        self.captured = captured
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def post(self, url, headers, json):
        self.captured.update({"url": url, "headers": headers, "body": json})
        return FakeResponse(self.content)


def configure_llm(monkeypatch):
    monkeypatch.setattr(llm_client, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(llm_client, "LLM_BASE_URL", "https://llm.example/v1/")
    monkeypatch.setattr(llm_client, "LLM_MODEL", "test-model")


def test_chat_json_uses_shared_request_pipeline(monkeypatch):
    configure_llm(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        llm_client.httpx,
        "Client",
        lambda timeout: FakeClient(captured, '```json\n{"answer": "ok"}\n```'),
    )

    result = llm_client._chat_json("system", "user", 0.25)

    assert result == {"answer": "ok"}
    assert captured["url"] == "https://llm.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["body"] == {
        "model": "test-model",
        "messages": [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ],
        "temperature": 0.25,
    }


def test_chat_completion_rejects_incomplete_configuration(monkeypatch):
    monkeypatch.setattr(llm_client, "LLM_API_KEY", "")
    monkeypatch.setattr(llm_client, "LLM_BASE_URL", "")
    monkeypatch.setattr(llm_client, "LLM_MODEL", "")

    with pytest.raises(RuntimeError, match="LLM 配置不完整"):
        llm_client._chat_completion("system", "user", 0.2)
