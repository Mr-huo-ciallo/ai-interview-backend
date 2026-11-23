import threading
import time

import main
from routers import career as career_router
from schemas import ResumeExtractionResult, ResumeStructuredData


def register_and_login(client, username="p1_user", password="password123"):
    client.post("/api/auth/register", json={"username": username, "password": password})
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}


def test_b05_resume_import_runs_in_threadpool(client, monkeypatch):
    headers = register_and_login(client, username="pdf_thread_user")
    called_via_threadpool = []

    async def fake_run_in_threadpool(func, *args, **kwargs):
        called_via_threadpool.append(func.__name__)
        return ResumeExtractionResult(
            rawText="张三\nPython FastAPI 后端工程师",
            structured=ResumeStructuredData(fullName="张三", skills=["Python", "FastAPI"]),
            warnings=[],
            extractionMethod="local_text+rules",
            pageCount=1,
            confidence=0.45,
        )

    monkeypatch.setattr(career_router, "run_in_threadpool", fake_run_in_threadpool)

    resp = client.post(
        "/api/career/resume/import",
        headers=headers,
        files={"file": ("resume.pdf", b"%PDF-1.4 sample content", "application/pdf")},
        data={"targetRole": "Python 开发"},
    )
    assert resp.status_code == 200
    assert called_via_threadpool == ["import_pdf"]
    assert resp.json()["extraction"]["structured"]["fullName"] == "张三"


def test_b07_report_generation_runs_llm_calls_in_parallel_and_caches_profile_ai(client, monkeypatch):
    headers = register_and_login(client, username="parallel_user")
    main._profile_ai_cache.clear()

    # 先写入一条历史记录，让报告生成时具备历史摘要
    add_resp = client.post(
        "/api/history/add",
        headers=headers,
        json={
            "role": "python",
            "roleName": "Python 开发",
            "totalScore": 80,
            "answerCount": 1,
            "submitTime": "2026-11-23 10:00",
            "answers": [
                {
                    "question": "如何定位接口性能问题？",
                    "type": "technical",
                    "answer": "先看监控与慢查询。",
                }
            ],
        },
    )
    assert add_resp.status_code == 200

    barrier = threading.Barrier(2, timeout=2.0)
    profile_calls = []

    def fake_feedback(payload):
        barrier.wait()
        return {
            "summary": "并行生成的报告总评",
            "historicalInsight": "历史表现稳定",
            "strengths": ["结构清晰"],
            "weaknesses": ["缺少量化数据"],
            "suggestions": ["补充压测指标"],
            "historicalSuggestions": ["持续练习场景题"],
            "questionReports": [],
        }

    def fake_profile(payload):
        profile_calls.append(payload["username"])
        barrier.wait()
        return {
            "aiSummary": "并行缓存的画像摘要",
            "aiSuggestions": ["继续强化性能排查"],
        }

    monkeypatch.setattr(main, "call_llm_for_feedback", fake_feedback)
    monkeypatch.setattr(main, "call_llm_for_profile_summary", fake_profile)

    started = time.perf_counter()
    report_resp = client.post(
        "/api/report/generate",
        headers=headers,
        json={
            "role": "python",
            "roleName": "Python 开发",
            "submitTime": "2026-11-23 14:40",
            "answers": [
                {
                    "question": "如何定位接口性能问题？",
                    "type": "technical",
                    "answer": "先看监控指标，再分析慢 SQL 与锁竞争。",
                }
            ],
        },
    )
    elapsed = time.perf_counter() - started
    assert report_resp.status_code == 200
    assert report_resp.json()["summary"] == "并行生成的报告总评"
    assert len(profile_calls) == 1
    assert elapsed < 2.0

    # 访问个人画像摘要应直接命中缓存，不再重复调用 LLM
    profile_resp = client.get("/api/profile/summary", headers=headers)
    assert profile_resp.status_code == 200
    assert profile_resp.json()["aiSummary"] == "并行缓存的画像摘要"
    assert len(profile_calls) == 1
