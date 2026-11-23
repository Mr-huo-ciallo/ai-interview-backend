import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from db import get_db
from dependencies import require_current_user
from schemas import (
    FollowUpCreateRequest,
    JobCreateRequest,
    JobImportConfirmRequest,
    JobImportRequest,
    JobJdParseRequest,
    JobStatusRequest,
    ResumeProfileRequest,
    ResumeVersionCreateRequest,
)
from services.career import CareerService
from services.resume_import import MAX_PDF_BYTES, LocalTextPdfResumeParser, ResumeImportError, ResumeImportService


router = APIRouter(prefix="/api/career", tags=["career"])
logger = logging.getLogger(__name__)


def get_career_service(current_user=Depends(require_current_user), db=Depends(get_db)):
    return CareerService(db, current_user.id)


@router.get("/dashboard")
def get_career_dashboard(service: CareerService = Depends(get_career_service)):
    return service.dashboard()


@router.put("/resume")
def upsert_resume(data: ResumeProfileRequest, service: CareerService = Depends(get_career_service)):
    return {"resume": service.save_resume(data.resumeText, data.targetRole)}


@router.post("/resume/import")
async def import_resume_pdf(
    file: UploadFile = File(...),
    targetRole: str = Form(""),
    _current_user=Depends(require_current_user),
):
    content = await file.read(MAX_PDF_BYTES + 1)
    try:
        parser_service = ResumeImportService(LocalTextPdfResumeParser())
        result = await run_in_threadpool(
            parser_service.import_pdf,
            content,
            file.filename or "resume.pdf",
            targetRole.strip(),
        )
    except ResumeImportError as exc:
        logger.warning("resume_pdf_import_failed reason=%s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        await file.close()
    logger.info(
        "resume_pdf_import_completed method=%s pages=%s warnings=%s",
        result.extractionMethod,
        result.pageCount,
        len(result.warnings),
    )
    return {"extraction": result.model_dump()}


@router.post("/jobs")
def add_career_job(data: JobCreateRequest, service: CareerService = Depends(get_career_service)):
    return {"job": service.add_job(data.model_dump())}


@router.post("/jobs/parse-jd")
def parse_career_job_jd(
    data: JobJdParseRequest,
    service: CareerService = Depends(get_career_service),
):
    return {"parsed": service.parse_job_jd(data.rawText, data.sourceUrl)}


@router.post("/jobs/import/preview")
def preview_career_jobs(
    data: JobImportRequest,
    service: CareerService = Depends(get_career_service),
):
    return service.preview_job_import(data.jobs)


@router.post("/jobs/import/confirm")
def confirm_career_jobs(
    data: JobImportConfirmRequest,
    service: CareerService = Depends(get_career_service),
):
    return service.confirm_job_import([job.model_dump() for job in data.jobs])


@router.patch("/jobs/{job_id}/status")
def change_career_job_status(
    job_id: int,
    data: JobStatusRequest,
    service: CareerService = Depends(get_career_service),
):
    return {"job": service.change_job_status(job_id, data.applicationStatus)}


@router.put("/jobs/{job_id}")
def update_career_job(
    job_id: int,
    data: JobCreateRequest,
    service: CareerService = Depends(get_career_service),
):
    return {"job": service.edit_job(job_id, data.model_dump())}


@router.delete("/jobs/{job_id}")
def delete_career_job(job_id: int, service: CareerService = Depends(get_career_service)):
    service.remove_job(job_id)
    return {"message": "职位已删除"}


@router.post("/jobs/{job_id}/follow-ups")
def add_job_follow_up(
    job_id: int,
    data: FollowUpCreateRequest,
    service: CareerService = Depends(get_career_service),
):
    return {"followUp": service.add_follow_up(job_id, data.dueAt, data.note)}


@router.patch("/follow-ups/{follow_up_id}/complete")
def finish_job_follow_up(follow_up_id: int, service: CareerService = Depends(get_career_service)):
    return {"followUp": service.finish_follow_up(follow_up_id)}


@router.post("/jobs/{job_id}/prepare")
def prepare_for_career_job(job_id: int, service: CareerService = Depends(get_career_service)):
    return {"jobId": job_id, "preparation": service.prepare_job(job_id)}


@router.post("/jobs/{job_id}/resume-draft")
def generate_tailored_resume_draft(job_id: int, service: CareerService = Depends(get_career_service)):
    return {"jobId": job_id, "draft": service.generate_resume_draft(job_id)}


@router.post("/jobs/{job_id}/interview-questions")
def generate_job_interview_questions(job_id: int, service: CareerService = Depends(get_career_service)):
    result = service.generate_interview_questions(job_id)
    return {"jobId": job_id, **result}


@router.post("/resume-versions")
def save_resume_version(
    data: ResumeVersionCreateRequest,
    service: CareerService = Depends(get_career_service),
):
    return {"version": service.save_resume_version(data.model_dump())}


@router.get("/action-plan")
def get_career_action_plan(service: CareerService = Depends(get_career_service)):
    return {"plan": service.action_plan()}
