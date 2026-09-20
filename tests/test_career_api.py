def register_and_login(client, username):
    register = client.post("/api/auth/register", json={"username": username, "password": "password"})
    assert register.status_code == 200
    login = client.post("/api/auth/login", json={"username": username, "password": "password"})
    assert login.status_code == 200
    token = login.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def test_career_dashboard_requires_login(client):
    response = client.get("/api/career/dashboard")
    assert response.status_code == 401


def test_user_can_manage_only_own_career_data(client):
    owner_headers = register_and_login(client, "owner")
    other_headers = register_and_login(client, "other")

    resume = client.put(
        "/api/career/resume",
        json={"resumeText": "熟悉 Vue TypeScript Docker，负责过管理后台项目。", "targetRole": "前端工程师"},
        headers=owner_headers,
    )
    assert resume.status_code == 200
    assert "Vue" in resume.json()["resume"]["skills"]

    created = client.post(
        "/api/career/jobs",
        json={"title": "Vue 前端工程师", "company": "示例公司", "requiredSkills": "Vue、TypeScript、React"},
        headers=owner_headers,
    )
    assert created.status_code == 200
    job_id = created.json()["job"]["id"]

    forbidden = client.patch(
        f"/api/career/jobs/{job_id}/status",
        json={"applicationStatus": "offer"},
        headers=other_headers,
    )
    assert forbidden.status_code == 404

    dashboard = client.get("/api/career/dashboard", headers=owner_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["summary"]["jobCount"] == 1
    assert dashboard.json()["jobs"][0]["match"]["score"] >= 0


def test_follow_up_lifecycle_is_scoped_to_owner(client):
    owner_headers = register_and_login(client, "follow-owner")
    other_headers = register_and_login(client, "follow-other")
    job = client.post(
        "/api/career/jobs",
        json={"title": "测试工程师", "company": "示例公司"},
        headers=owner_headers,
    ).json()["job"]

    created = client.post(
        f"/api/career/jobs/{job['id']}/follow-ups",
        json={"dueAt": "2026-08-01T10:00", "note": "确认招聘流程进展"},
        headers=owner_headers,
    )
    assert created.status_code == 200
    follow_up_id = created.json()["followUp"]["id"]

    assert client.patch(f"/api/career/follow-ups/{follow_up_id}/complete", headers=other_headers).status_code == 404
    assert client.patch(f"/api/career/follow-ups/{follow_up_id}/complete", headers=owner_headers).status_code == 200

    dashboard = client.get("/api/career/dashboard", headers=owner_headers).json()
    assert dashboard["followUps"] == []


def test_career_generation_endpoints_do_not_require_request_body(client):
    headers = register_and_login(client, "career-generator")
    resume = client.put(
        "/api/career/resume",
        json={"resumeText": "熟悉 Vue、Python 和 Docker。", "targetRole": "全栈工程师"},
        headers=headers,
    )
    assert resume.status_code == 200

    created = client.post(
        "/api/career/jobs",
        json={"title": "全栈工程师", "company": "示例公司", "requiredSkills": "Vue、Python、Docker"},
        headers=headers,
    )
    assert created.status_code == 200
    job_id = created.json()["job"]["id"]

    assert client.post(f"/api/career/jobs/{job_id}/prepare", headers=headers).status_code == 200
    assert client.post(f"/api/career/jobs/{job_id}/resume-draft", headers=headers).status_code == 200
    assert client.post(f"/api/career/jobs/{job_id}/interview-questions", headers=headers).status_code == 200
