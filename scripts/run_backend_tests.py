from __future__ import annotations

import os
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=BACKEND, env=env, check=True)


def main() -> int:
    # CI provides its own disposable PostgreSQL service. Locally, always create
    # a short-lived database so tests never downgrade a developer database.
    is_ci = os.environ.get("CI", "").lower() == "true"
    database_url = os.environ.get("DATABASE_URL") if is_ci else None
    container_name: str | None = None
    environment = os.environ.copy()

    if not is_ci:
        container_name = f"vaievolta-tests-{uuid.uuid4().hex[:12]}"
        subprocess.run(
            [
                "docker", "run", "--detach", "--rm", "--name", container_name,
                "--publish", "127.0.0.1::5432", "--env", "POSTGRES_USER=test",
                "--env", "POSTGRES_PASSWORD=test", "--env", "POSTGRES_DB=test",
                "postgres:18-alpine",
            ],
            check=True,
            cwd=ROOT,
        )
        try:
            port_output = subprocess.check_output(
                ["docker", "port", container_name, "5432/tcp"], text=True, cwd=ROOT
            ).strip()
            port = port_output.rsplit(":", maxsplit=1)[-1]
            for _ in range(60):
                ready = subprocess.run(
                    ["docker", "exec", container_name, "pg_isready", "-U", "test", "-d", "test"],
                    cwd=ROOT,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                if ready.returncode == 0:
                    break
                time.sleep(1)
            else:
                raise RuntimeError("PostgreSQL descartável não ficou pronto em 60 segundos")

            database_url = f"postgresql+psycopg://test:test@127.0.0.1:{port}/test"
            environment["DATABASE_URL"] = database_url
            environment.setdefault("APP_ENV", "test")
            environment.setdefault("JWT_SECRET", "local-test-secret-not-for-production")
            for _ in range(60):
                ready = subprocess.run(
                    [
                        "uv", "run", "python", "-c",
                        "import os, psycopg; u=os.environ['DATABASE_URL'].replace('postgresql+psycopg://', 'postgresql://', 1); c=psycopg.connect(u, connect_timeout=2); c.execute('SELECT 1'); c.close()",
                    ],
                    cwd=BACKEND,
                    env=environment,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                if ready.returncode == 0:
                    break
                time.sleep(1)
            else:
                raise RuntimeError("PostgreSQL descartável não aceitou conexões em 60 segundos")
            run(["uv", "run", "alembic", "upgrade", "head"], env=environment)
        except BaseException:
            subprocess.run(["docker", "rm", "--force", container_name], cwd=ROOT, check=False)
            raise
    elif not database_url:
        raise RuntimeError("CI precisa definir DATABASE_URL para executar os testes do backend")

    try:
        run(["uv", "run", "pytest", "--cov=app", "--cov-report=xml"], env=environment)
    finally:
        if container_name:
            subprocess.run(["docker", "rm", "--force", container_name], cwd=ROOT, check=False)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode) from error
