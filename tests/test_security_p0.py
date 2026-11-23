import httpx

import llm_client
from db import SessionLocal
from models import UserModel


def register_and_login(client, username, password="password123"):
    client.post("/api/auth/register", json={"username": username, "password": password})
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}, resp.json()["user"]


def test_b01_admin_questions_requires_admin_role(client):
    # 未登录返回 401
    assert client.get("/api/admin/questions").status_code == 401
    assert client.post(
        "/api/admin/questions",
        json={"role": "python", "type": "technical", "content": "匿名写题"},
    ).status_code == 401

    # 普通用户返回 403
    user_headers, user = register_and_login(client, "normal_user")
    assert user["isAdmin"] is False
    assert client.get("/api/admin/questions", headers=user_headers).status_code == 403
    assert client.post(
        "/api/admin/questions",
        headers=user_headers,
        json={"role": "python", "type": "technical", "content": "普通用户写题"},
    ).status_code == 403

    # 数据库提升为管理员后可正常访问
    with SessionLocal.begin() as db:
        record = db.query(UserModel).filter_by(username="normal_user").first()
        record.is_admin = True

    allowed = client.post(
        "/api/admin/questions",
        headers=user_headers,
        json={"role": "python", "type": "technical", "content": "管理员写题"},
    )
    assert allowed.status_code == 200
    qid = allowed.json()["question"]["id"]
    assert client.delete(f"/api/admin/questions/{qid}", headers=user_headers).status_code == 200


def test_b02_ssrf_blocks_private_and_metadata_urls_in_production(client, monkeypatch):
    headers, _ = register_and_login(client, "ssrf_user")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("LLM_ALLOWED_PRIVATE_HOSTS", raising=False)

    for dangerous_url in (
        "http://127.0.0.1:11434/v1",
        "http://localhost:11434/v1",
        "http://10.0.0.5:8080/v1",
        "http://192.168.1.10/v1",
        "http://169.254.169.254/latest/meta-data",
        "http://metadata.google.internal/computeMetadata/v1",
    ):
        resp = client.put(
            "/api/settings/llm",
            headers=headers,
            json={
                "provider": "custom",
                "apiFormat": "openai",
                "baseUrl": dangerous_url,
                "model": "test-model",
                "apiKey": "",
                "enabled": True,
            },
        )
        assert resp.status_code == 400, f"expected 400 for {dangerous_url}, got {resp.status_code}"

    # 配置白名单后允许放行自建 Ollama
    monkeypatch.setenv("LLM_ALLOWED_PRIVATE_HOSTS", "localhost,127.0.0.1")
    allowed = client.put(
        "/api/settings/llm",
        headers=headers,
        json={
            "provider": "custom",
            "apiFormat": "openai",
            "baseUrl": "http://127.0.0.1:11434/v1",
            "model": "qwen2.5:14b",
            "apiKey": "",
            "enabled": True,
        },
    )
    assert allowed.status_code == 200


def test_b02_connection_test_does_not_echo_upstream_response_body(client, monkeypatch):
    headers, _ = register_and_login(client, "echo_user")

    class ErrorResponse:
        status_code = 500
        text = "INTERNAL_SECRET_BANNER_12345"

        def raise_for_status(self):
            request = httpx.Request("POST", "https://llm.example/v1/chat/completions")
            raise httpx.HTTPStatusError("server error", request=request, response=self)

    class ErrorClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, headers, json):
            return ErrorResponse()

    monkeypatch.setattr(llm_client.httpx, "Client", lambda timeout: ErrorClient())

    resp = client.post(
        "/api/settings/llm/test",
        headers=headers,
        json={
            "provider": "openai",
            "apiFormat": "openai",
            "baseUrl": "https://llm.example/v1",
            "model": "gpt-4o-mini",
            "apiKey": "sk-test-1234567890",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "INTERNAL_SECRET_BANNER_12345" not in data["message"]
    assert "500" in data["message"]


def test_b03_rate_limiting_returns_429_for_llm_endpoints(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_FOLLOWUP_MAX", "2")
    monkeypatch.setenv("RATE_LIMIT_REPORT_MAX", "2")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setattr("routers.questions.call_llm_for_followup", lambda payload: "")
    monkeypatch.setattr("routers.reports.call_llm_for_feedback", lambda payload: (_ for _ in ()).throw(RuntimeError("offline")))

    followup_payload = {
        "role": "python",
        "roleName": "Python 开发",
        "question": "如何定位接口性能问题？",
        "type": "technical",
        "answer": "先分析监控数据。",
    }
    assert client.post("/api/interview/follow-up", json=followup_payload).status_code == 200
    assert client.post("/api/interview/follow-up", json=followup_payload).status_code == 200
    third_followup = client.post("/api/interview/follow-up", json=followup_payload)
    assert third_followup.status_code == 429
    assert "Retry-After" in third_followup.headers

    report_payload = {
        "role": "python",
        "roleName": "Python 开发",
        "submitTime": "2026-11-23 14:30",
        "answers": [
            {
                "question": "如何定位接口性能问题？",
                "type": "technical",
                "answer": "先看监控指标，再排查慢查询和锁竞争。",
            }
        ],
    }
    assert client.post("/api/report/generate", json=report_payload).status_code == 200
    assert client.post("/api/report/generate", json=report_payload).status_code == 200
    third_report = client.post("/api/report/generate", json=report_payload)
    assert third_report.status_code == 429
    assert "Retry-After" in third_report.headers
