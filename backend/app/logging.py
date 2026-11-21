"""Logging estruturado em JSON no stdout, com redação de dados sensíveis.

Nunca registrar senha, CPF, e-mail, telefone, endereço, token ou corpo de
requisição (Documento Técnico 8.6; Kit 6.2 e 12.3).
"""

import json
import logging
import re
import sys
import traceback
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

REDACTED = "[REDACTED]"
REQUEST_FIELDS = ("request_id", "method", "route", "status_code", "duration_ms")

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

_SENSITIVE_SUBSTRINGS = (
    "password",
    "senha",
    "token",
    "secret",
    "authorization",
    "cookie",
    "email",
    "phone",
    "telefone",
    "address",
    "endereco",
)
_SENSITIVE_EXACT = frozenset(
    {
        "cpf",
        "cep",
        "body",
        "street",
        "rua",
        "complement",
        "complemento",
        "neighborhood",
        "bairro",
        "full_name",
        "nome_completo",
    }
)

_KEYS = "password|senha|token|cpf|email|e-mail|phone|telefone|authorization|cookie|secret"
_TEXT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?i)([\"']?(?:" + _KEYS + r")[\"']?\s*[:=]\s*)"
            r"(?:(?:bearer|basic|digest|negotiate)\s+)?"
            r"(?:\"[^\"]*\"|'[^']*'|[^\s,;&}]+)"
        ),
        r"\1" + REDACTED,
    ),
    (re.compile(r"(?i)bearer\s+[\w.\-~+/=]+"), REDACTED),
    (re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+"), REDACTED),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*"), REDACTED),
    (re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)"), REDACTED),
    (re.compile(r"(?<!\d)\(?\d{2}\)?\s?9\d{4}-?\d{4}(?!\d)"), REDACTED),
)

_STANDARD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


def is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in _SENSITIVE_EXACT or any(
        part in normalized for part in _SENSITIVE_SUBSTRINGS
    )


def redact_text(text: str) -> str:
    for pattern, replacement in _TEXT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_value(key: str, value: Any) -> Any:
    if is_sensitive_key(key):
        return REDACTED
    if isinstance(value, dict):
        return {str(k): redact_value(str(k), v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [redact_value(key, v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds")
        data: dict[str, Any] = {
            "timestamp": timestamp.replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
            "request_id": getattr(record, "request_id", None) or request_id_ctx.get(),
        }
        for field in REQUEST_FIELDS[1:]:
            if hasattr(record, field):
                data[field] = redact_value(field, getattr(record, field))
        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS or key in data or key.startswith("_"):
                continue
            data[key] = redact_value(key, value)
        if record.exc_info and record.exc_info[0] is not None:
            # Só o tipo e o stack; a mensagem da exceção pode conter dados.
            exc_type, _, tb = record.exc_info
            data["exc_type"] = exc_type.__name__
            data["stack"] = redact_text("".join(traceback.format_tb(tb)))
        return json.dumps(data, ensure_ascii=False, default=str)


_HANDLER_FLAG = "_vv_json_handler"


def configure_logging(level: str = "INFO") -> None:
    """Emite JSON no stdout. Idempotente: troca só o handler que criou."""
    root = logging.getLogger()
    for existing in list(root.handlers):
        if getattr(existing, _HANDLER_FLAG, False):
            root.removeHandler(existing)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    setattr(handler, _HANDLER_FLAG, True)
    root.addHandler(handler)
    root.setLevel(level.upper())

    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
    # O access log do uvicorn inclui a query string; o middleware o substitui.
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False
    access.disabled = True
