def register_and_login(client, username="s01_user", password="password123"):
    client.post("/api/auth/register", json={"username": username, "password": password})
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}


def test_s01_parse_jd_rule_fallback_extracts_fields(client, monkeypatch):
    headers = register_and_login(client, username="jd_parse_user")
    monkeypatch.setattr(
        "services.career.call_llm_for_jd_parse",
        lambda raw_text: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    raw_jd = """
    职位名称：高级 Python 后端工程师
    公司名称：星辰科技
    工作地点：上海 | 薪资：25-35K
    岗位职责：
    1. 负责核心 FastAPI 微服务架构设计与性能优化
    2. 参与 MySQL 与 Redis 高并发数据层治理
    任职要求：
    1. 熟练掌握 Python、FastAPI、MySQL、Redis、Docker
    加分项：
    1. 有 Kubernetes 或高并发分布式系统经验
    """
    resp = client.post(
        "/api/career/jobs/parse-jd",
        headers=headers,
        json={"rawText": raw_jd, "sourceUrl": "https://example.com/job/1"},
    )
    assert resp.status_code == 200
    parsed = resp.json()["parsed"]
    assert parsed["source"] == "rule"
    assert parsed["title"] == "高级 Python 后端工程师"
    assert parsed["company"] == "星辰科技"
    assert parsed["location"] == "上海"
    assert parsed["salary"] == "25-35K"
    assert "Python" in parsed["requiredSkills"]
    assert "FastAPI" in parsed["requiredSkills"]
    assert len(parsed["responsibilities"]) >= 2
    assert len(parsed["mustHave"]) >= 1
    assert len(parsed["niceToHave"]) >= 1


def test_s01_job_specific_questions_score_in_feature_matrix_and_link_history(client, monkeypatch):
    headers = register_and_login(client, username="job_interview_user")
    monkeypatch.setattr(
        "services.career.call_llm_for_job_interview_questions",
        lambda payload: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    monkeypatch.setattr(
        "routers.reports.call_llm_for_feedback",
        lambda payload: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    assert client.put(
        "/api/career/resume",
        headers=headers,
        json={"resumeText": "3年后端开发，熟练掌握 Python, FastAPI, MySQL, Redis", "targetRole": "Python 后端"},
    ).status_code == 200

    job_resp = client.post(
        "/api/career/jobs",
        headers=headers,
        json={
            "title": "Python 后端工程师",
            "company": "星辰科技",
            "requiredSkills": "Python,FastAPI,Redis,Docker",
        },
    )
    assert job_resp.status_code == 200
    job_id = job_resp.json()["job"]["id"]

    # 1. 生成职位专属面试题，校验携带关键点与评分重点元数据
    q_resp = client.post(f"/api/career/jobs/{job_id}/interview-questions", headers=headers)
    assert q_resp.status_code == 200
    questions = q_resp.json()["questions"]
    assert len(questions) == 5
    first_q = questions[0]
    assert first_q["keyPoints"]
    assert first_q["scoringFocus"]
    assert first_q["tags"]

    # 2. 提交职位专属题答案（题目不在固定题库中），验证特征矩阵命中了透传的关键点
    report_resp = client.post(
        "/api/report/generate",
        headers=headers,
        json={
            "jobId": job_id,
            "jobTitle": "Python 后端工程师",
            "role": "python",
            "roleName": "JD 专项 · Python 后端工程师",
            "submitTime": "2026-11-23 19:20",
            "answers": [
                {
                    "question": first_q["content"],
                    "type": first_q["type"],
                    "difficulty": first_q["difficulty"],
                    "tags": first_q["tags"],
                    "keyPoints": first_q["keyPoints"],
                    "scoringFocus": first_q["scoringFocus"],
                    "referenceAnswerBasic": first_q["referenceAnswerBasic"],
                    "answer": "我在这个项目中负责核心模块，使用 Python 和 FastAPI 完成关键实现，并通过缓存优化取得了接口延迟降低 40% 的量化结果。",
                }
            ],
        },
    )
    assert report_resp.status_code == 200
    report = report_resp.json()
    assert report["jobId"] == job_id
    assert report["jobTitle"] == "Python 后端工程师"
    features = report["featureMatrix"][0]["features"]
    assert features["keyPointCoverage"] > 0
    assert len(features["coveredKeyPoints"]) > 0

    # 3. 保存历史并验证按 job_id 过滤
    save_hist = client.post(
        "/api/history/add",
        headers=headers,
        json={
            "jobId": job_id,
            "jobTitle": "Python 后端工程师",
            "role": "python",
            "roleName": "JD 专项 · Python 后端工程师",
            "totalScore": report["totalScore"],
            "answerCount": 1,
            "submitTime": "2026-11-23 19:20",
            "answers": [{"question": first_q["content"], "type": first_q["type"], "answer": "回答"}],
            "featureMatrix": report["featureMatrix"],
            "scoreMeta": report["scoreMeta"],
        },
    )
    assert save_hist.status_code == 200

    # 再保存一条不关联职位的普通模拟面试
    assert client.post(
        "/api/history/add",
        headers=headers,
        json={
            "role": "java",
            "roleName": "Java 后端",
            "totalScore": 70,
            "answerCount": 1,
            "submitTime": "2026-11-23 19:25",
            "answers": [{"question": "什么是 JVM？", "type": "technical", "answer": "虚拟机"}],
        },
    ).status_code == 200

    all_hist = client.get("/api/history/list", headers=headers).json()["history"]
    assert len(all_hist) == 2

    job_hist = client.get("/api/history/list", headers=headers, params={"job_id": job_id}).json()["history"]
    assert len(job_hist) == 1
    assert job_hist[0]["jobId"] == job_id
    assert job_hist[0]["jobTitle"] == "Python 后端工程师"
