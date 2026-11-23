from collections import Counter
import json
from pathlib import Path

import pytest

from scoring.config import SUPPORTED_ROLES
from scoring.judgement import build_judgement_request, parse_judgement
from scoring.matrix import build_feature_matrix


SAMPLES = json.loads(
    (Path(__file__).parent / "fixtures" / "scoring_regression.json").read_text(encoding="utf-8")
)["samples"]


def _labels_as_llm_output(request: list[dict], labels: list[dict]) -> dict:
    ids = {(p["kind"], p["point"]): p["id"] for q in request for p in q["points"]}
    return {
        "judgements": [
            {"id": ids[(label["kind"], label["point"])], "status": label["status"], "evidence": label["evidence"]}
            for label in labels
        ]
    }


def score_sample(sample: dict, judged: bool) -> dict:
    answers = [sample["item"]]
    judgements = {}
    if judged:
        request = build_judgement_request(answers)
        judgements = parse_judgement(request, _labels_as_llm_output(request, sample["labels"]))
    row = build_feature_matrix(sample["role"], answers, judgements)["questionRows"][0]
    return {**row["features"], **row["dimensionScores"]}


@pytest.mark.parametrize("sample", SAMPLES, ids=[s["id"] for s in SAMPLES])
def test_labels_survive_evidence_validation(sample):
    result = score_sample(sample, judged=True)
    statuses = {(a["kind"], a["point"]): a["status"] for a in result["keyPointAssessments"]}
    for label in sample["labels"]:
        assert statuses[(label["kind"], label["point"])] == label["status"]
    assert result["judgementSource"] == "llm"


@pytest.mark.parametrize("sample", SAMPLES, ids=[s["id"] for s in SAMPLES])
def test_judged_scores_stay_within_expected_ranges(sample):
    result = score_sample(sample, judged=True)
    for metric, (low, high) in sample["expected"].items():
        assert low <= result[metric] <= high, f"{metric}={result[metric]} not in [{low}, {high}]"


def test_regression_samples_cover_all_roles():
    counts = Counter(sample["role"] for sample in SAMPLES)
    for role in SUPPORTED_ROLES:
        assert counts[role] >= 3, f"role {role} has only {counts[role]} samples, expected >= 3"
    assert all(sample.get("reviewed") is True for sample in SAMPLES)


def test_judgement_fixes_known_lexical_errors():
    by_id = {s["id"]: s for s in SAMPLES}
    synonyms = by_id["java-cache-synonyms"]
    stuffing = by_id["java-cache-keyword-stuffing"]

    assert score_sample(synonyms, judged=False)["keyPointCoverage"] < 0.5
    assert score_sample(stuffing, judged=False)["keyPointCoverage"] == 1.0
    assert score_sample(synonyms, judged=True)["tech"] > score_sample(stuffing, judged=True)["tech"]


def _request_for(answer: str, followup: str = "") -> list[dict]:
    return build_judgement_request([{
        "question": "Q",
        "answer": answer,
        "followUpAnswer": followup,
        "keyPoints": "索引；事务",
        "scoringFocus": "",
    }])


def test_parse_judgement_downgrades_fabricated_evidence_and_ignores_unknown_ids():
    request = _request_for("我会给查询字段加联合索引来加速。")
    parsed = parse_judgement(request, {"judgements": [
        {"id": "q1-k1", "status": "covered", "evidence": "给查询字段加联合 索引"},
        {"id": "q1-k2", "status": "covered", "evidence": "使用事务保证一致性"},
        {"id": "q9-k1", "status": "covered", "evidence": "x"},
        {"id": "q1-k1", "status": "unknown", "evidence": ""},
    ]})

    assert parsed[1][("keyPoint", "索引")]["status"] == "covered"
    assert parsed[1][("keyPoint", "索引")]["foundIn"] == "main"
    assert parsed[1][("keyPoint", "事务")] == {"status": "missing", "evidence": "", "foundIn": ""}
    assert set(parsed) == {1}


def test_omitted_points_fall_back_to_lexical_matching():
    answers = [{"question": "Q", "answer": "用事务保证原子性。", "keyPoints": "索引；事务", "scoringFocus": ""}]
    request = build_judgement_request(answers)
    parsed = parse_judgement(request, {"judgements": [{"id": "q1-k1", "status": "missing", "evidence": ""}]})
    features = build_feature_matrix("java", answers, parsed)["questionRows"][0]["features"]
    sources = {a["point"]: a["source"] for a in features["keyPointAssessments"]}

    assert sources == {"索引": "llm", "事务": "lexical"}
    assert features["judgementSource"] == "mixed"
    assert features["coveredKeyPoints"] == ["事务"]


def test_report_uses_llm_judgement_and_records_scoring_version(client, monkeypatch):
    sample = next(s for s in SAMPLES if s["id"] == "java-cache-synonyms")
    captured = {}

    def fake_judgement(request):
        captured["request"] = request
        return _labels_as_llm_output(request, sample["labels"])

    def fake_feedback(payload):
        return {"questionReports": [{"question": "Q", "comment": "c", "coveredKeyPoints": [], "missingKeyPoints": ["缓存穿透"], "advice": "a"}]}

    monkeypatch.setattr("routers.reports.call_llm_for_keypoint_judgement", fake_judgement)
    monkeypatch.setattr("routers.reports.call_llm_for_feedback", fake_feedback)

    response = client.post("/api/report/generate", json={
        "role": "java",
        "roleName": "Java 后端",
        "submitTime": "2026-11-23 20:00",
        "answers": [sample["item"]],
    })

    assert response.status_code == 200
    report = response.json()
    assert [p["id"] for p in captured["request"][0]["points"]] == ["q1-k1", "q1-k2", "q1-k3", "q1-f1"]
    assert report["scoreMeta"]["scoringVersion"] == "2026.11-s02.2"
    assert report["scoreMeta"]["judgementSource"] == "llm"
    assert report["scoreMeta"]["matrixWeight"] == 1.0
    assert report["scoreMeta"]["scoreSource"] == "feature_matrix"
    features = report["featureMatrix"][0]["features"]
    assert features["keyPointCoverage"] == 1.0
    assert all(a["evidence"] for a in features["keyPointAssessments"])
    assert report["questionReports"][0]["coveredKeyPoints"] == ["缓存穿透", "缓存击穿", "缓存雪崩"]
    assert report["questionReports"][0]["partialKeyPoints"] == []
    assert report["questionReports"][0]["missingKeyPoints"] == []


def test_report_falls_back_to_lexical_when_judgement_fails(client, monkeypatch):
    monkeypatch.setattr(
        "routers.reports.call_llm_for_keypoint_judgement",
        lambda request: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    monkeypatch.setattr(
        "routers.reports.call_llm_for_feedback",
        lambda payload: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    stuffing = next(s for s in SAMPLES if s["id"] == "java-cache-keyword-stuffing")

    response = client.post("/api/report/generate", json={
        "role": "java",
        "roleName": "Java 后端",
        "submitTime": "2026-11-23 20:00",
        "answers": [stuffing["item"]],
    })

    assert response.status_code == 200
    assert response.json()["scoreMeta"]["judgementSource"] == "lexical"
    assert response.json()["scoreMeta"]["matrixWeight"] == 0.85
    assert response.json()["featureMatrix"][0]["features"]["keyPointCoverage"] == 1.0


def test_parse_judgement_normalizes_punctuation_and_keeps_first_duplicate():
    request = _request_for("首先，给查询字段加联合索引；其次用事务保证原子性。")
    parsed = parse_judgement(request, {"judgements": [
        {"id": "q1-k1", "status": "covered", "evidence": "首先, 给查询字段加联合索引;"},
        {"id": "q1-k1", "status": "missing", "evidence": ""},
        {"id": "q1-k2", "status": "partial", "evidence": "用事务保证原子性"},
    ]})

    assert parsed[1][("keyPoint", "索引")]["status"] == "covered"
    assert parsed[1][("keyPoint", "事务")]["status"] == "partial"


def test_partial_split_followup_half_credit_and_empty_answer_boundaries():
    # partial in follow-up should stay out of coveredKeyPoints and give 0.5 followupGain
    answers = [{
        "question": "Q1",
        "type": "scenario",
        "answer": "先定位慢 SQL。",
        "followUpAnswer": "后面再考虑一下事务。",
        "keyPoints": "索引；事务",
        "scoringFocus": "",
    }]
    request = build_judgement_request(answers)
    parsed = parse_judgement(request, {"judgements": [
        {"id": "q1-k1", "status": "covered", "evidence": "先定位慢 SQL"},
        {"id": "q1-k2", "status": "partial", "evidence": "考虑一下事务"},
    ]})
    features = build_feature_matrix("java", answers, parsed)["questionRows"][0]["features"]
    assert features["coveredKeyPoints"] == ["索引"]
    assert features["partialKeyPoints"] == ["事务"]
    assert features["missingKeyPoints"] == []
    assert features["followupGain"] == 0.5

    # empty answer and no-keyPoints-with-followup boundaries
    empty_row = build_feature_matrix("java", [{"question": "Q2", "answer": "", "keyPoints": "索引"}])["questionRows"][0]
    assert empty_row["dimensionScores"] == {"tech": 0, "expression": 0, "logic": 0, "match": 0}
    no_kp_row = build_feature_matrix("java", [{
        "question": "Q3",
        "answer": "基础说明",
        "followUpAnswer": "在项目中补充了具体的压测数据与限流降级方案，验证了系统稳定性。",
        "keyPoints": "",
    }])["questionRows"][0]
    assert no_kp_row["features"]["followupGain"] > 0


def test_report_aligns_out_of_order_llm_question_reports(client, monkeypatch):
    monkeypatch.setattr(
        "routers.reports.call_llm_for_keypoint_judgement",
        lambda request: {"judgements": [
            {"id": "q1-k1", "status": "covered", "evidence": "布隆过滤器"},
            {"id": "q2-k1", "status": "missing", "evidence": ""},
        ]},
    )
    monkeypatch.setattr(
        "routers.reports.call_llm_for_feedback",
        lambda payload: {"questionReports": [
            {"question": "第二题", "comment": "第二题点评", "coveredKeyPoints": ["伪造点"], "advice": "第二题建议"},
            {"question": "第一题", "comment": "第一题点评", "coveredKeyPoints": [], "advice": "第一题建议"},
        ]},
    )

    response = client.post("/api/report/generate", json={
        "role": "java",
        "roleName": "Java 后端",
        "submitTime": "2026-11-23 21:00",
        "answers": [
            {"question": "第一题", "type": "technical", "keyPoints": "缓存穿透", "answer": "用布隆过滤器防穿透"},
            {"question": "第二题", "type": "technical", "keyPoints": "索引失效", "answer": "不太清楚"},
        ],
    })

    assert response.status_code == 200
    reports = response.json()["questionReports"]
    assert len(reports) == 2
    assert reports[0]["question"] == "第一题"
    assert reports[0]["comment"] == "第一题点评"
    assert reports[0]["coveredKeyPoints"] == ["缓存穿透"]
    assert reports[1]["question"] == "第二题"
    assert reports[1]["comment"] == "第二题点评"
    assert reports[1]["coveredKeyPoints"] == []
    assert reports[1]["missingKeyPoints"] == ["索引失效"]
