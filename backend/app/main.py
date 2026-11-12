from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes.auth import router as auth_router
from app.errors import ApiError
from app.migrations import upgrade_database


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    upgrade_database()
    yield


app = FastAPI(title="Vai e Volta API", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return field errors without echoing request values such as passwords."""
    fields: dict[str, str] = {}
    for error in exc.errors():
        location = [str(part) for part in error["loc"] if part not in {"body", "query", "path"}]
        field = ".".join(location) or "body"
        error_type = error["type"]
        context = error.get("ctx", {})
        if error_type == "missing":
            message = "Campo obrigatório."
        elif error_type == "string_too_short":
            message = f"Informe no mínimo {context.get('min_length')} caracteres."
        elif error_type == "string_too_long":
            message = f"Informe no máximo {context.get('max_length')} caracteres."
        elif field == "email":
            message = "E-mail inválido."
        elif field == "state":
            message = "UF inválida."
        elif error_type == "extra_forbidden":
            message = "Campo não permitido."
        elif error_type == "json_invalid":
            message = "JSON inválido."
        else:
            message = "Formato inválido."
        fields.setdefault(field, message)
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Revise os campos informados.",
                "fields": fields,
            }
        },
    )


@app.exception_handler(ApiError)
async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "fields": exc.fields,
            }
        },
    )
