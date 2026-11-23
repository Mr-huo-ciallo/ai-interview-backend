import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import validate_runtime_config
from observability import RequestLoggingMiddleware, configure_logging, get_request_id
from routers.auth import router as auth_router
from routers.career import router as career_router
from routers.health import router as health_router
from routers.history import router as history_router
from routers.llm_settings import router as llm_settings_router
from routers.questions import router as questions_router
from routers.reports import router as reports_router


app = FastAPI()

configure_logging()
validate_runtime_config()

raw_cors_origins = os.getenv("CORS_ORIGINS", "*")
cors_origins = [
    origin.strip()
    for origin in raw_cors_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(auth_router)
app.include_router(career_router)
app.include_router(health_router)
app.include_router(history_router)
app.include_router(llm_settings_router)
app.include_router(questions_router)
app.include_router(reports_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    response = {"detail": exc.detail, "requestId": get_request_id(request)}
    return JSONResponse(status_code=exc.status_code, content=response, headers=exc.headers)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.getLogger("api.error").exception(
        "unhandled request error requestId=%s path=%s", get_request_id(request), request.url.path
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "服务器内部错误", "requestId": get_request_id(request)},
    )


@app.get("/")
def read_root():
    return {"message": "AI Interview Backend is running"}
