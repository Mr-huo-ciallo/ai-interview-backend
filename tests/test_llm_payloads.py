from llm_payloads import QUESTION_CONTEXT_FIELDS, build_job_context, build_question_context


def test_build_question_context_keeps_only_prompt_fields():
    question_meta = {field: f"value-{field}" for field in QUESTION_CONTEXT_FIELDS}
    question_meta["id"] = 42

    context = build_question_context(question_meta)

    assert set(context) == set(QUESTION_CONTEXT_FIELDS)
    assert context["difficulty"] == "value-difficulty"
    assert "id" not in context


def test_build_question_context_uses_empty_values_without_metadata():
    assert build_question_context(None) == {field: "" for field in QUESTION_CONTEXT_FIELDS}


def test_build_job_context_maps_shared_prompt_fields():
    match = {"score": 80}

    assert build_job_context(
        {"resumeText": "熟悉 Python"},
        {
            "title": "后端工程师",
            "company": "示例公司",
            "requiredSkills": "Python、Docker",
            "description": "负责接口开发",
        },
        match,
    ) == {
        "resumeText": "熟悉 Python",
        "jobTitle": "后端工程师",
        "company": "示例公司",
        "jobRequirements": "Python、Docker",
        "jobDescription": "负责接口开发",
        "match": match,
    }
