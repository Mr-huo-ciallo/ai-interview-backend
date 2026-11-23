def question_payload(content="如何定位接口性能问题？"):
    return {
        "role": "python",
        "type": "technical",
        "content": content,
        "difficulty": "medium",
        "tags": "Python,性能",
    }


def admin_headers(client, monkeypatch, username="admin_user"):
    monkeypatch.setenv("ADMIN_USERNAMES", username)
    client.post("/api/auth/register", json={"username": username, "password": "password123"})
    login = client.post("/api/auth/login", json={"username": username, "password": "password123"})
    assert login.status_code == 200
    assert login.json()["user"]["isAdmin"] is True
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def test_question_crud_routes_keep_existing_contract(client, monkeypatch):
    headers = admin_headers(client, monkeypatch)
    created = client.post("/api/admin/questions", headers=headers, json=question_payload())
    assert created.status_code == 200
    question_id = created.json()["question"]["id"]

    listed = client.get("/api/questions", params={"role": "python"})
    assert listed.status_code == 200
    assert listed.json()["questions"][0]["content"] == "如何定位接口性能问题？"

    updated = client.put(
        f"/api/admin/questions/{question_id}",
        headers=headers,
        json=question_payload("如何系统定位接口性能瓶颈？"),
    )
    assert updated.status_code == 200
    assert updated.json()["question"]["content"] == "如何系统定位接口性能瓶颈？"

    deleted = client.delete(f"/api/admin/questions/{question_id}", headers=headers)
    assert deleted.status_code == 200
    assert client.get("/api/questions", params={"role": "python"}).json()["questions"] == []


def test_follow_up_route_uses_fallback_when_llm_returns_empty(client, monkeypatch):
    monkeypatch.setattr("routers.questions.call_llm_for_followup", lambda payload: "")

    response = client.post(
        "/api/interview/follow-up",
        json={
            "role": "python",
            "roleName": "Python 开发",
            "question": "如何定位接口性能问题？",
            "type": "technical",
            "answer": "先分析监控数据。",
        },
    )

    assert response.status_code == 200
    assert response.json()["followUpQuestion"] == "你能进一步解释一下这个技术点背后的原理或适用场景吗？"
