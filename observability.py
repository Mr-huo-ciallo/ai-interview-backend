import json
import logging
import os
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


REQUEST_ID_HEADER = "X-Request-ID"


def configure_logging():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=False,
    )


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.logger = logging.getLogger("api.access")

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id
        started_at = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            self.logger.exception(
                json.dumps({"requestId": request_id, "method": request.method, "path": request.url.path})
            )
            raise

        duration_ms = round((time.perf_counter() - started_at) * 1000, 1)
        response.headers[REQUEST_ID_HEADER] = request_id
        self.logger.info(json.dumps({
            "requestId": request_id,
            "method": request.method,
            "path": request.url.path,
            "statusCode": response.status_code,
            "durationMs": duration_ms,
        }, ensure_ascii=False))
        return response
