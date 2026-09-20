QUESTION_CONTEXT_FIELDS = (
    "difficulty",
    "tags",
    "keyPoints",
    "scoringFocus",
    "referenceAnswerBasic",
    "referenceAnswerGood",
    "followupFocus",
    "followupExamples",
)


def build_question_context(question_meta: dict | None) -> dict:
    return {
        field: question_meta.get(field) if question_meta else ""
        for field in QUESTION_CONTEXT_FIELDS
    }


def build_job_context(resume: dict, job: dict, match: dict) -> dict:
    return {
        "resumeText": resume["resumeText"],
        "jobTitle": job["title"],
        "company": job["company"],
        "jobRequirements": job["requiredSkills"],
        "jobDescription": job["description"],
        "match": match,
    }
