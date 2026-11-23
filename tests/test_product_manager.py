from collections import Counter

import llm_client
from db import SessionLocal
from models import InterviewQuestionModel
from scoring.matrix import build_feature_matrix, extract_features
from seed import product_manager


def test_seed_has_balanced_original_questions():
    questions = product_manager.load_questions()

    assert len(questions) == 30
    assert Counter(question["dimension"] for question in questions) == {
        "用户研究": 5, "需求优先级": 5, "产品设计": 5,
        "数据指标": 5, "交付协作": 5, "项目复盘": 5,
    }
    assert Counter(question["difficulty"] for question in questions) == {
        "easy": 6, "medium": 15, "hard": 9,
    }


def test_seed_is_insert_only_and_question_api_can_read_role(client, monkeypatch):
    monkeypatch.setattr("sys.argv", ["seed.product_manager", "--apply"])
    product_manager.main()
    first = client.get("/api/questions", params={"role": "product_manager"})
    assert first.status_code == 200
    assert len(first.json()["questions"]) == 30

    with SessionLocal.begin() as db:
        question = db.query(InterviewQuestionModel).filter_by(role="product_manager").first()
        question.reference_answer_good = "管理员修订后的回答"

    product_manager.main()
    with SessionLocal() as db:
        questions = db.query(InterviewQuestionModel).filter_by(role="product_manager").all()
        assert len(questions) == 30
        assert questions[0].reference_answer_good == "管理员修订后的回答"


def test_product_answer_uses_product_depth_instead_of_java_terms():
    question = product_manager.load_questions()[0]
    context = {
        **question,
        "answer": "先做用户访谈，明确使用场景和真实痛点，再比较替代方案，用实验验证用户价值与风险。",
    }
    product = extract_features("product_manager", context)
    java = extract_features("java", context)

    assert product["technicalDepth"] > java["technicalDepth"]
    assert product["keyPointCoverage"] > 0


def test_product_prompts_ask_for_product_judgment():
    payload = {
        "role": "product_manager", "roleName": "互联网产品经理",
        "type": "technical", "question": "如何验证需求？", "answer": "先访谈用户。",
    }
    assert "产品经理面试评估助手" in llm_client.build_prompt(payload)
    prompt = llm_client.build_prompt({**payload, "scores": {"techScore": 70}, "featureMatrix": [{"features": {"technicalDepth": 0.8}}]})
    assert '"产品判断分": 70' in prompt
    assert '"产品分析深度": 0.8' in prompt
    assert "techScore" not in prompt
    assert "technicalDepth" not in prompt
    assert "用户证据" in llm_client.build_followup_prompt(payload)
    assert "技术面试官" not in llm_client.build_followup_prompt(payload)


def test_product_scoring_prefers_evidence_based_answer():
    question = product_manager.load_questions()[0]
    weak = build_feature_matrix("product_manager", [{**question, "answer": "直接加排行榜。"}])
    strong = build_feature_matrix("product_manager", [{
        **question,
        "answer": (
            "首先确定目标用户和使用场景，通过用户访谈观察当前做法，区分真实痛点与排行榜方案。"
            "其次用行为数据与分群确认问题规模，比较推荐卡片等替代方案的用户价值、成本和风险。"
            "最后明确实验假设、成功指标与数据口径，灰度验证后复盘并迭代。"
        ),
    }])

    assert strong["scores"]["totalScore"] > weak["scores"]["totalScore"]
    assert strong["questionRows"][0]["features"]["keyPointCoverage"] > weak["questionRows"][0]["features"]["keyPointCoverage"]


def test_product_report_fallback_does_not_recommend_java(client, monkeypatch):
    monkeypatch.setattr("routers.reports.call_llm_for_feedback", lambda payload: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setenv("ADMIN_USERNAMES", "pm_admin")
    client.post("/api/auth/register", json={"username": "pm_admin", "password": "password123"})
    login = client.post("/api/auth/login", json={"username": "pm_admin", "password": "password123"})
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    question = product_manager.load_questions()[0]
    created = client.post("/api/admin/questions", headers=headers, json={
        "role": "product_manager", "type": question["type"], "content": question["content"],
        "difficulty": question["difficulty"], "tags": question["tags"],
        "keyPoints": question["keyPoints"], "scoringFocus": question["scoringFocus"],
        "referenceAnswerGood": question["referenceAnswerGood"],
    })
    assert created.status_code == 200

    response = client.post("/api/report/generate", json={
        "role": "product_manager", "roleName": "互联网产品经理", "submitTime": "2026-10-13 10:00",
        "answers": [{
            "question": question["content"], "type": question["type"],
            "answer": "先做用户访谈，明确使用场景和真实痛点，再比较替代方案，用实验验证结果。",
        }],
    })
    assert response.status_code == 200
    report = response.json()
    assert report["role"] == "product_manager"
    assert "用户证据" in report["summary"]
    assert "Spring" not in " ".join(report["suggestions"])

    monkeypatch.setattr("routers.questions.call_llm_for_followup", lambda payload: "")
    followup = client.post("/api/interview/follow-up", json={
        "role": "product_manager", "roleName": "互联网产品经理",
        "type": "technical", "question": question["content"], "answer": "先访谈用户。",
    })
    assert followup.json()["followUpQuestion"] == "你会用哪些证据支持这个产品判断？"
