import logging

from fastapi import HTTPException
from pydantic import ValidationError

from crud import (
    complete_follow_up,
    create_follow_up,
    create_job,
    create_jobs,
    create_resume_version,
    delete_job,
    get_job_by_id,
    get_jobs_by_user,
    get_pending_follow_ups,
    get_resume_profile,
    get_resume_versions,
    save_resume_profile,
    update_job,
    update_job_status,
)
from services.career_rules import (
    build_daily_action_plan,
    build_job_interview_questions,
    build_job_preparation,
    score_job_match,
)
from llm_client import (
    call_llm_for_daily_action_plan,
    call_llm_for_job_interview_questions,
    call_llm_for_job_preparation,
    call_llm_for_tailored_resume,
)
from llm_payloads import build_job_context
from schemas import JobCreateRequest


logger = logging.getLogger(__name__)
ALLOWED_JOB_STATUSES = {"saved", "applied", "interviewing", "offer", "rejected"}


class CareerService:
    def __init__(self, db, user_id: int):
        self.db = db
        self.user_id = user_id

    def _resume(self):
        return get_resume_profile(self.db, self.user_id)

    def _job(self, job_id: int):
        job = get_job_by_id(self.db, self.user_id, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="职位不存在")
        return job

    def dashboard(self):
        resume = self._resume()
        jobs = get_jobs_by_user(self.db, self.user_id)
        enriched_jobs = [{**job, "match": score_job_match(resume, job)} for job in jobs]
        status_counts = {status: 0 for status in ALLOWED_JOB_STATUSES}
        for job in enriched_jobs:
            status = job["applicationStatus"]
            status_counts[status] = status_counts.get(status, 0) + 1
        average_match = (
            round(sum(job["match"]["score"] for job in enriched_jobs) / len(enriched_jobs))
            if enriched_jobs
            else 0
        )
        progressed_count = sum(status_counts[status] for status in ("applied", "interviewing", "offer", "rejected"))
        interview_count = status_counts["interviewing"] + status_counts["offer"]
        return {
            "resume": resume,
            "jobs": enriched_jobs,
            "resumeVersions": get_resume_versions(self.db, self.user_id),
            "followUps": get_pending_follow_ups(self.db, self.user_id),
            "summary": {
                "jobCount": len(enriched_jobs),
                "averageMatch": average_match,
                "statusCounts": status_counts,
                "funnel": {
                    "stages": [
                        {"key": "saved", "label": "已收藏", "count": status_counts["saved"]},
                        {"key": "applied", "label": "已投递", "count": status_counts["applied"]},
                        {"key": "interviewing", "label": "进入面试", "count": status_counts["interviewing"]},
                        {"key": "offer", "label": "已获 Offer", "count": status_counts["offer"]},
                    ],
                    "progressedCount": progressed_count,
                    "interviewRate": round(interview_count / progressed_count * 100) if progressed_count else 0,
                    "offerRate": round(status_counts["offer"] / progressed_count * 100) if progressed_count else 0,
                },
            },
        }

    def save_resume(self, resume_text: str, target_role: str):
        if not resume_text.strip():
            raise HTTPException(status_code=400, detail="简历内容不能为空")
        return save_resume_profile(self.db, self.user_id, resume_text.strip(), target_role.strip())

    def add_job(self, data: dict):
        self._validate_job(data)
        job = create_job(self.db, self.user_id, data)
        return {**job, "match": score_job_match(self._resume(), job)}

    def preview_job_import(self, items: list[dict]):
        if not items:
            raise HTTPException(status_code=400, detail="JSON 中没有可导入的职位")
        if len(items) > 100:
            raise HTTPException(status_code=400, detail="单次最多导入 100 个职位")

        existing_keys = {self._job_key(job) for job in get_jobs_by_user(self.db, self.user_id)}
        file_keys = set()
        preview = []
        for index, raw_item in enumerate(items):
            errors = []
            normalized = None
            if not isinstance(raw_item, dict):
                errors.append("职位必须是 JSON 对象")
            else:
                try:
                    normalized = JobCreateRequest.model_validate(raw_item).model_dump()
                    self._validate_job(normalized)
                except ValidationError as exc:
                    errors.extend(error["msg"] for error in exc.errors())
                except HTTPException as exc:
                    errors.append(str(exc.detail))

            duplicate = False
            if normalized:
                key = self._job_key(normalized)
                duplicate = key in existing_keys or key in file_keys
                file_keys.add(key)
            preview.append({
                "index": index,
                "valid": not errors,
                "duplicate": duplicate,
                "errors": errors,
                "job": normalized or raw_item,
            })
        return {
            "items": preview,
            "summary": {
                "total": len(preview),
                "valid": sum(1 for item in preview if item["valid"] and not item["duplicate"]),
                "duplicate": sum(1 for item in preview if item["duplicate"]),
                "invalid": sum(1 for item in preview if not item["valid"]),
            },
        }

    def confirm_job_import(self, items: list[dict]):
        preview = self.preview_job_import(items)
        importable = [item["job"] for item in preview["items"] if item["valid"] and not item["duplicate"]]
        if not importable:
            raise HTTPException(status_code=400, detail="没有可导入的职位")
        created = create_jobs(self.db, self.user_id, importable)
        resume = self._resume()
        return {
            "jobs": [{**job, "match": score_job_match(resume, job)} for job in created],
            "importedCount": len(created),
            "skippedCount": len(items) - len(created),
        }

    def change_job_status(self, job_id: int, application_status: str):
        if application_status not in ALLOWED_JOB_STATUSES:
            raise HTTPException(status_code=400, detail="不支持的职位状态")
        job = update_job_status(self.db, self.user_id, job_id, application_status)
        if not job:
            raise HTTPException(status_code=404, detail="职位不存在")
        return {**job, "match": score_job_match(self._resume(), job)}

    def edit_job(self, job_id: int, data: dict):
        self._validate_job(data)
        job = update_job(self.db, self.user_id, job_id, data)
        if not job:
            raise HTTPException(status_code=404, detail="职位不存在")
        return {**job, "match": score_job_match(self._resume(), job)}

    def remove_job(self, job_id: int):
        if not delete_job(self.db, self.user_id, job_id):
            raise HTTPException(status_code=404, detail="职位不存在")

    def add_follow_up(self, job_id: int, due_at: str, note: str):
        if not due_at.strip() or not note.strip():
            raise HTTPException(status_code=400, detail="请填写跟进时间和跟进事项")
        self._job(job_id)
        return create_follow_up(self.db, self.user_id, job_id, due_at.strip(), note.strip())

    def finish_follow_up(self, follow_up_id: int):
        follow_up = complete_follow_up(self.db, self.user_id, follow_up_id)
        if not follow_up:
            raise HTTPException(status_code=404, detail="跟进事项不存在")
        return follow_up

    def prepare_job(self, job_id: int):
        resume = self._require_resume("请先保存简历，再生成职位准备建议")
        job = self._job(job_id)
        match = score_job_match(resume, job)
        preparation = build_job_preparation(resume, job, match)
        try:
            llm_result = call_llm_for_job_preparation(build_job_context(resume, job, match))
            if llm_result.get("summary"):
                preparation = llm_result
        except Exception:
            logger.warning("职位准备建议 AI 生成失败，已回退到规则建议", exc_info=True)
        return preparation

    def generate_resume_draft(self, job_id: int):
        resume = self._require_resume("请先保存原始简历，再生成定制草稿")
        job = self._job(job_id)
        match = score_job_match(resume, job)
        draft = {
            "source": "rule",
            "title": f"{job['company']} · {job['title']} · 简历草稿",
            "content": resume["resumeText"],
        }
        try:
            draft = call_llm_for_tailored_resume(build_job_context(resume, job, match))
        except Exception:
            logger.warning("定制简历草稿 AI 生成失败，已回退到原始简历", exc_info=True)
        return draft

    def generate_interview_questions(self, job_id: int):
        resume = self._require_resume("请先保存简历，再生成 JD 专项面试题")
        job = self._job(job_id)
        match = score_job_match(resume, job)
        questions = build_job_interview_questions(job, match)
        source = "rule"
        try:
            llm_questions = call_llm_for_job_interview_questions(build_job_context(resume, job, match))
            if llm_questions:
                questions = llm_questions
                source = "llm"
        except Exception:
            logger.warning("JD 专项面试题 AI 生成失败，已回退到规则题目", exc_info=True)
        return {"source": source, "questions": questions}

    def save_resume_version(self, data: dict):
        if not data["title"].strip() or not data["content"].strip():
            raise HTTPException(status_code=400, detail="版本名称和简历内容不能为空")
        if data.get("jobId"):
            self._job(data["jobId"])
        return create_resume_version(self.db, self.user_id, data)

    def action_plan(self):
        resume = self._resume()
        jobs = get_jobs_by_user(self.db, self.user_id)
        enriched_jobs = [{**job, "match": score_job_match(resume, job)} for job in jobs]
        plan = build_daily_action_plan(resume, enriched_jobs)
        try:
            llm_result = call_llm_for_daily_action_plan({
                "resume": resume,
                "jobs": enriched_jobs,
                "rulePlan": plan,
            })
            if llm_result.get("summary"):
                plan = llm_result
        except Exception:
            logger.warning("每日行动计划 AI 生成失败，已回退到规则计划", exc_info=True)
        return plan

    def _require_resume(self, detail: str):
        resume = self._resume()
        if not resume:
            raise HTTPException(status_code=400, detail=detail)
        return resume

    @staticmethod
    def _validate_job(data: dict):
        if not data["title"].strip() or not data["company"].strip():
            raise HTTPException(status_code=400, detail="职位名称和公司名称不能为空")

    @staticmethod
    def _job_key(data: dict):
        source_url = str(data.get("sourceUrl", "")).strip().casefold()
        if source_url:
            return ("url", source_url)
        return (
            "fields",
            str(data.get("company", "")).strip().casefold(),
            str(data.get("title", "")).strip().casefold(),
            str(data.get("location", "")).strip().casefold(),
        )
