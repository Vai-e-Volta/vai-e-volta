import json
import logging
from io import StringIO

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.logging import JsonFormatter, redact_text
from app.main import create_app

SENSITIVE = [
    "Segredo@123",
    "11144477735",
    "tok-abc.def.ghi",
    "ana.silva@exemplo.test",
    "53991110001",
    "SESSAO-SECRETA",
]


@pytest.fixture
def captured():
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    target = logging.getLogger("app.request")
    target.addHandler(handler)
    yield stream
    target.removeHandler(handler)


def make_app():
    cfg = Settings(
        _env_file=None,
        JWT_SECRET="x" * 32,
        POSTGRES_PASSWORD="fake",
        APP_ENV="test",
    )
    app = create_app(cfg)

    @app.post("/api/_echo")
    def echo():
        return {"ok": True}

    return app


def test_API_SEC_01_requisicao_com_dados_sensiveis_nao_vai_para_o_log(captured):
    client = TestClient(make_app())
    client.post(
        "/api/_echo?email=ana.silva@exemplo.test",
        json={
            "senha": SENSITIVE[0],
            "cpf": SENSITIVE[1],
            "token": SENSITIVE[2],
            "email": SENSITIVE[3],
            "telefone": SENSITIVE[4],
        },
        headers={
            "Authorization": f"Bearer {SENSITIVE[2]}",
            "Cookie": f"vv_session={SENSITIVE[5]}",
        },
    )
    output = captured.getvalue()
    assert output
    for value in SENSITIVE:
        assert value not in output


def test_API_SEC_02_log_tem_campos_minimos_em_json(captured):
    client = TestClient(make_app())
    client.get("/api/health", headers={"X-Request-ID": "req-12345678"})
    record = json.loads(captured.getvalue().splitlines()[-1])
    for field in (
        "request_id",
        "method",
        "route",
        "status_code",
        "duration_ms",
        "level",
        "timestamp",
        "logger",
    ):
        assert field in record
    assert record["request_id"] == "req-12345678"
    assert record["method"] == "GET"
    assert record["route"] == "/api/health"


def test_API_SEC_03_request_id_invalido_e_substituido(captured):
    client = TestClient(make_app())
    response = client.get("/api/health", headers={"X-Request-ID": "x\ninjetado"})
    assert response.headers["X-Request-ID"] != "x\ninjetado"
    assert len(response.headers["X-Request-ID"]) == 32


def test_API_SEC_04_formatter_mascara_mensagem_e_campos_extras():
    logger = logging.getLogger("teste.redacao")
    logger.propagate = False
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        logger.info(
            "login cpf=11144477735 de ana.silva@exemplo.test",
            extra={"password": "Segredo@123", "dados": {"phone": "53991110001"}},
        )
    finally:
        logger.removeHandler(handler)
    output = stream.getvalue()
    for value in ("11144477735", "ana.silva@exemplo.test", "Segredo@123", "53991110001"):
        assert value not in output


def test_API_SEC_05_excecao_registra_stack_sem_mensagem_com_dados():
    logger = logging.getLogger("teste.excecao")
    logger.propagate = False
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    try:
        try:
            raise ValueError("cpf 11144477735 senha=Segredo@123")
        except ValueError:
            logger.error("falha", exc_info=True)
    finally:
        logger.removeHandler(handler)
    record = json.loads(stream.getvalue())
    assert record["exc_type"] == "ValueError"
    assert "11144477735" not in stream.getvalue()
    assert "Segredo@123" not in stream.getvalue()


def test_API_SEC_06_redact_text_mascara_bearer_e_jwt():
    text = "Authorization: Bearer abc.def eyJhbGci.eyJzdWI.sig"
    out = redact_text(text)
    assert "abc.def" not in out
    assert "eyJhbGci" not in out
