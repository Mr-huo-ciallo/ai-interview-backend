import llm_client


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, captured, payload):
        self.captured = captured
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def post(self, url, headers, json):
        self.captured.update({"url": url, "headers": headers, "body": json})
        return FakeResponse(self.payload)


def register_and_login(client, username="api_user", password="password123"):
    client.post("/api/auth/register", json={"username": username, "password": password})
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    token = resp.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def test_list_llm_providers(client):
    response = client.get("/api/settings/llm/providers")
    assert response.status_code == 200
    providers = response.json()["providers"]
    provider_ids = {item["id"] for item in providers}
    assert {"deepseek", "openai", "qwen", "zhipu", "moonshot", "gemini", "anthropic", "custom"}.issubset(provider_ids)


def test_save_update_mask_and_delete_user_llm_config(client):
    headers = register_and_login(client)

    initial = client.get("/api/settings/llm", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["config"] is None

    saved = client.put(
        "/api/settings/llm",
        headers=headers,
        json={
            "provider": "deepseek",
            "apiFormat": "openai",
            "baseUrl": "https://api.deepseek.com/v1/",
            "model": "deepseek-chat",
            "apiKey": "sk-1234567890abcdef",
            "enabled": True,
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["effectiveSource"] == "user"
    assert body["config"]["provider"] == "deepseek"
    assert body["config"]["baseUrl"] == "https://api.deepseek.com/v1"
    assert body["config"]["hasApiKey"] is True
    assert body["config"]["apiKeyMasked"] == "sk-1****cdef"
    assert "sk-1234567890abcdef" not in str(body)

    # Updating without apiKey preserves existing encrypted key
    updated = client.put(
        "/api/settings/llm",
        headers=headers,
        json={
            "provider": "deepseek",
            "apiFormat": "openai",
            "baseUrl": "https://api.deepseek.com/v1",
            "model": "deepseek-reasoner",
            "apiKey": "",
            "enabled": True,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["config"]["model"] == "deepseek-reasoner"
    assert updated.json()["config"]["apiKeyMasked"] == "sk-1****cdef"

    deleted = client.delete("/api/settings/llm", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["config"] is None


def test_user_llm_config_injected_into_followup_and_supports_anthropic(client, monkeypatch):
    headers = register_and_login(client, username="claude_user")
    captured = {}

    monkeypatch.setattr(
        llm_client.httpx,
        "Client",
        lambda timeout: FakeClient(
            captured,
            {"content": [{"type": "text", "text": "你如何衡量这次改版的留存提升？"}]},
        ),
    )

    save_resp = client.put(
        "/api/settings/llm",
        headers=headers,
        json={
            "provider": "anthropic",
            "apiFormat": "anthropic",
            "baseUrl": "https://api.anthropic.com/v1",
            "model": "claude-3-5-sonnet-latest",
            "apiKey": "sk-ant-test-key-9999",
            "enabled": True,
        },
    )
    assert save_resp.status_code == 200

    followup_resp = client.post(
        "/api/interview/follow-up",
        headers=headers,
        json={
            "role": "product_manager",
            "roleName": "互联网产品经理",
            "question": "请介绍一个你主导的需求",
            "type": "project",
            "answer": "我负责了首页改版，优化了核心转化路径。",
        },
    )
    assert followup_resp.status_code == 200
    assert followup_resp.json()["followUpQuestion"] == "你如何衡量这次改版的留存提升？"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "sk-ant-test-key-9999"
    assert captured["body"]["model"] == "claude-3-5-sonnet-latest"


def test_custom_local_api_allows_empty_key_and_connection_test(client, monkeypatch):
    headers = register_and_login(client, username="ollama_user")
    captured = {}

    monkeypatch.setattr(
        llm_client.httpx,
        "Client",
        lambda timeout: FakeClient(
            captured,
            {"choices": [{"message": {"content": "OK"}}]},
        ),
    )

    test_resp = client.post(
        "/api/settings/llm/test",
        headers=headers,
        json={
            "provider": "custom",
            "apiFormat": "openai",
            "baseUrl": "http://localhost:11434/v1",
            "model": "qwen2.5:14b",
            "apiKey": "",
        },
    )
    assert test_resp.status_code == 200
    result = test_resp.json()
    assert result["ok"] is True
    assert "replyPreview" not in result
    assert captured["url"] == "http://localhost:11434/v1/chat/completions"
    assert "Authorization" not in captured["headers"]
