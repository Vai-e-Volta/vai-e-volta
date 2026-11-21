import pytest
from pydantic import ValidationError

from app.config import Settings, load_settings

VALID_SECRET = "x" * 32
BASE = {"JWT_SECRET": VALID_SECRET, "POSTGRES_PASSWORD": "fake"}


def make(**overrides):
    return Settings(_env_file=None, **{**BASE, **overrides})


def test_API_CONFIG_01_jwt_secret_menor_que_32_falha():
    with pytest.raises(ValidationError):
        make(JWT_SECRET="x" * 31)


def test_API_CONFIG_02_jwt_secret_com_32_caracteres_passa():
    assert make().JWT_SECRET.get_secret_value() == VALID_SECRET


def test_API_CONFIG_03_sem_jwt_secret_falha_com_mensagem_clara(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError) as exc:
        load_settings(_env_file=None, POSTGRES_PASSWORD="fake")
    assert "JWT_SECRET" in str(exc.value)


def test_API_CONFIG_04_mensagem_de_erro_nao_vaza_o_segredo():
    with pytest.raises(RuntimeError) as exc:
        load_settings(_env_file=None, JWT_SECRET="segredo-curto", POSTGRES_PASSWORD="fake")
    assert "segredo-curto" not in str(exc.value)
    assert "32" in str(exc.value)


def test_API_CONFIG_05_sem_senha_do_banco_nem_database_url_falha(monkeypatch):
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, JWT_SECRET=VALID_SECRET)


def test_API_CONFIG_06_database_url_e_montada_com_senha_escapada(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    url = make(POSTGRES_PASSWORD="p@ss/word").database_url
    assert url == "postgresql+psycopg://vaievolta:p%40ss%2Fword@db:5432/vaievolta"


def test_API_CONFIG_07_database_url_informada_dispensa_senha_do_banco(monkeypatch):
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    cfg = Settings(
        _env_file=None,
        JWT_SECRET=VALID_SECRET,
        DATABASE_URL="postgresql+psycopg://u:p@localhost:5432/t",
    )
    assert cfg.database_url.endswith("@localhost:5432/t")


def test_API_CONFIG_08_valores_padrao_da_tabela_14_1(monkeypatch):
    for name in ("APP_ENV", "LOG_LEVEL", "TZ", "WEB_PORT"):
        monkeypatch.delenv(name, raising=False)
    cfg = make()
    assert (cfg.APP_ENV, cfg.LOG_LEVEL, cfg.TZ, cfg.WEB_PORT) == (
        "dev",
        "INFO",
        "America/Sao_Paulo",
        8080,
    )
    assert (cfg.JWT_EXPIRES_DAYS, cfg.COOKIE_SECURE) == (15, False)
    assert (cfg.LOGIN_MAX_ATTEMPTS, cfg.LOGIN_WINDOW_MINUTES, cfg.LOGIN_LOCK_MINUTES) == (5, 15, 15)
    assert (cfg.PROPOSAL_TTL_HOURS, cfg.ACCOUNT_RETENTION_DAYS) == (48, 365)
    assert (cfg.UPLOAD_DIR, cfg.MAX_UPLOAD_MB, cfg.MAX_PHOTOS) == ("/data/uploads", 5, 5)


@pytest.mark.parametrize(
    "overrides",
    [{"APP_ENV": "staging"}, {"LOG_LEVEL": "VERBOSE"}, {"TZ": "Marte/Olympus"}],
)
def test_API_CONFIG_09_valores_invalidos_falham(overrides):
    with pytest.raises(ValidationError):
        make(**overrides)
