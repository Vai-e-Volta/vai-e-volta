"""Configuração centralizada da API (Documento Técnico, seção 14.1).

Único ponto de leitura de variáveis de ambiente: nenhum outro módulo deve
usar ``os.environ`` diretamente. Segredos não têm valor padrão.
"""

from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

JWT_SECRET_MIN_LENGTH = 32
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

# .env na raiz do repositório (uso local, ex.: `make openapi`) e no diretório
# atual. Em contêiner as variáveis vêm do ambiente e os arquivos não existem.
_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_ROOT_ENV, ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Banco
    POSTGRES_DB: str = "vaievolta"
    POSTGRES_USER: str = "vaievolta"
    POSTGRES_PASSWORD: SecretStr | None = None
    # Montada pelo Compose; se ausente, é montada a partir de POSTGRES_*.
    DATABASE_URL: SecretStr | None = None

    # Sessão (RN-13)
    JWT_SECRET: SecretStr  # obrigatória, sem padrão
    JWT_EXPIRES_DAYS: int = Field(default=15, ge=1)
    COOKIE_SECURE: bool = False

    # Bloqueio de login (RN-14)
    LOGIN_MAX_ATTEMPTS: int = Field(default=5, ge=1)
    LOGIN_WINDOW_MINUTES: int = Field(default=15, ge=1)
    LOGIN_LOCK_MINUTES: int = Field(default=15, ge=1)

    # Regras de tempo (RN-47, RN-21)
    PROPOSAL_TTL_HOURS: int = Field(default=48, ge=1)
    ACCOUNT_RETENTION_DAYS: int = Field(default=365, ge=1)

    # Upload (RN-56)
    UPLOAD_DIR: str = "/data/uploads"
    MAX_UPLOAD_MB: int = Field(default=5, ge=1)
    MAX_PHOTOS: int = Field(default=5, ge=1)

    # Ambiente
    TZ: str = "America/Sao_Paulo"
    APP_ENV: Literal["dev", "test", "prod"] = "dev"
    LOG_LEVEL: str = "INFO"
    WEB_PORT: int = Field(default=8080, ge=1, le=65535)

    @field_validator("JWT_SECRET")
    @classmethod
    def _validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        # A mensagem nunca inclui o valor informado.
        if len(value.get_secret_value()) < JWT_SECRET_MIN_LENGTH:
            raise ValueError(f"deve ter no mínimo {JWT_SECRET_MIN_LENGTH} caracteres")
        return value

    @field_validator("LOG_LEVEL")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        level = value.strip().upper()
        if level not in LOG_LEVELS:
            raise ValueError(f"deve ser um de: {', '.join(LOG_LEVELS)}")
        return level

    @field_validator("TZ")
    @classmethod
    def _validate_tz(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("fuso horário desconhecido") from None
        return value

    @model_validator(mode="after")
    def _ensure_database_url(self) -> "Settings":
        url = self.DATABASE_URL
        if url is not None and url.get_secret_value():
            return self
        password = self.POSTGRES_PASSWORD
        if password is None or not password.get_secret_value():
            raise ValueError("defina DATABASE_URL ou POSTGRES_PASSWORD")
        user = quote_plus(self.POSTGRES_USER)
        pwd = quote_plus(password.get_secret_value())
        self.DATABASE_URL = SecretStr(
            f"postgresql+psycopg://{user}:{pwd}@db:5432/{self.POSTGRES_DB}"
        )
        return self

    @property
    def database_url(self) -> str:
        assert self.DATABASE_URL is not None  # garantido pelo validador
        return self.DATABASE_URL.get_secret_value()


def load_settings(**overrides: object) -> Settings:
    """Carrega a configuração; em erro, falha com mensagem clara.

    A mensagem lista só o nome da variável e o motivo, nunca o valor
    recebido (evita vazar segredo em log de inicialização).
    """
    try:
        return Settings(**overrides)  # type: ignore[arg-type]
    except ValidationError as exc:
        lines = [
            f"  - {'.'.join(str(p) for p in err['loc']) or 'configuração'}: {err['msg']}"
            for err in exc.errors()
        ]
        raise RuntimeError(
            "Configuração inválida; corrija o .env / as variáveis de ambiente:\n" + "\n".join(lines)
        ) from None


settings = load_settings()
