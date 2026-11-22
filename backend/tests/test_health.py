import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.db import get_db
from app.main import create_app


class OkSession:
    def execute(self, statement):
        return None


class BrokenSession:
    def execute(self, statement):
        raise OperationalError("SELECT 1", {}, Exception("host=db-interno senha=x"))


def make_settings(env: str) -> Settings:
    return Settings(_env_file=None, JWT_SECRET="x" * 32, POSTGRES_PASSWORD="fake", APP_ENV=env)


def client_with(session, env: str = "test") -> TestClient:
    app = create_app(make_settings(env))
    app.dependency_overrides[get_db] = lambda: session
    return TestClient(app)


def test_API_HEALTH_01_banco_ok_retorna_200_sem_autenticacao():
    response = client_with(OkSession()).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    assert "X-Request-ID" in response.headers


def test_API_HEALTH_02_banco_indisponivel_retorna_503_sem_detalhes():
    response = client_with(BrokenSession()).get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "error"}
    assert "db-interno" not in response.text


@pytest.mark.parametrize("env", ["test", "prod"])
def test_API_CONFIG_10_docs_e_openapi_retornam_404_fora_de_dev(env):
    client = client_with(OkSession(), env)
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_API_CONFIG_11_docs_e_openapi_funcionam_em_dev():
    client = client_with(OkSession(), "dev")
    assert client.get("/docs").status_code == 200
    assert "/api/health" in client.get("/openapi.json").json()["paths"]


@pytest.mark.parametrize("env", ["dev", "test", "prod"])
def test_API_CONFIG_12_app_openapi_independe_do_ambiente(env):
    app = create_app(make_settings(env))
    assert "/api/health" in app.openapi()["paths"]
