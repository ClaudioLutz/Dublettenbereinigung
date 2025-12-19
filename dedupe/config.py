from __future__ import annotations

from dataclasses import dataclass
import os


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "y"}


@dataclass(frozen=True)
class DbConfig:
    server: str
    database: str
    user: str
    password: str
    driver: str = "ODBC Driver 17 for SQL Server"
    trust_server_certificate: bool = True
    encrypt: bool = True

    @staticmethod
    def from_env(prefix: str = "DEDUPE_DB_") -> "DbConfig":
        server = os.environ[f"{prefix}SERVER"]
        database = os.environ[f"{prefix}DATABASE"]
        user = os.environ[f"{prefix}USER"]
        password = os.environ[f"{prefix}PASSWORD"]

        driver = os.getenv(f"{prefix}DRIVER", "ODBC Driver 17 for SQL Server")
        encrypt = _as_bool(os.getenv(f"{prefix}ENCRYPT", "true"), True)
        trust_server_certificate = _as_bool(
            os.getenv(f"{prefix}TRUST_SERVER_CERTIFICATE", "true"), True
        )

        return DbConfig(
            server=server,
            database=database,
            user=user,
            password=password,
            driver=driver,
            trust_server_certificate=trust_server_certificate,
            encrypt=encrypt,
        )
