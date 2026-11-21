"""Middleware de request_id e log de requisição (sem corpo, headers ou query)."""

import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.logging import request_id_ctx

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{8,64}")

logger = logging.getLogger("app.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if _SAFE_REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        token = request_id_ctx.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # exc_info: o formatter registra só o tipo e o stack, sem a mensagem.
            self._log(request, request_id, 500, started, exc_info=True)
            request_id_ctx.reset(token)
            raise
        response.headers[REQUEST_ID_HEADER] = request_id
        self._log(request, request_id, response.status_code, started)
        request_id_ctx.reset(token)
        return response

    @staticmethod
    def _log(
        request: Request,
        request_id: str,
        status_code: int,
        started: float,
        exc_info: bool = False,
    ) -> None:
        route = request.scope.get("route")
        path = getattr(route, "path", None) or request.url.path
        if status_code >= 500:
            level = logging.ERROR
        elif status_code in (409, 429):
            level = logging.WARNING
        else:
            level = logging.INFO
        logger.log(
            level,
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "route": path,
                "status_code": status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
            exc_info=exc_info,
        )
