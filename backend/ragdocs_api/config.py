import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "storage" / "uploads"
CHROMA_DIR = BASE_DIR / "storage" / "chroma"
INDEX_VERSION = "ragdocs_v2"

load_dotenv(BASE_DIR / ".env")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)


def get_env_int(name, default):
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


def normalize_origin(origin):
    return origin.strip().rstrip("/")


def get_cors_origins():
    raw_origins = os.getenv("FRONTEND_URLS", "").strip()
    if not raw_origins:
        raw_origins = os.getenv("FRONTEND_URL", "*").strip()

    if raw_origins == "*":
        return "*"

    origins = [
        normalize_origin(origin)
        for origin in raw_origins.split(",")
        if origin.strip()
    ]
    return origins or "*"


def build_database_uri():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return database_url

    mysql_host = os.getenv("MYSQL_HOST", "").strip()
    mysql_port = os.getenv("MYSQL_PORT", "3306").strip()
    mysql_user = os.getenv("MYSQL_USER", "").strip()
    mysql_password = os.getenv("MYSQL_PASSWORD", "")
    mysql_database = os.getenv("MYSQL_DATABASE", "").strip()

    if all([mysql_host, mysql_user, mysql_database]):
        encoded_password = quote_plus(mysql_password)
        return (
            f"mysql+pymysql://{mysql_user}:{encoded_password}"
            f"@{mysql_host}:{mysql_port}/{mysql_database}?charset=utf8mb4"
        )

    return f"sqlite:///{BASE_DIR / 'ragdocs.db'}"


def build_engine_options():
    database_uri = build_database_uri()
    options = {
        "pool_pre_ping": True,
        "pool_recycle": get_env_int("DB_POOL_RECYCLE_SECONDS", 240),
    }

    if database_uri.startswith("mysql+pymysql://"):
        options["pool_timeout"] = get_env_int("DB_POOL_TIMEOUT_SECONDS", 30)
        if os.getenv("MYSQL_SSL_MODE", "").strip().upper() == "REQUIRED":
            options["connect_args"] = {"ssl": {}}

    return options


class Config:
    SQLALCHEMY_DATABASE_URI = build_database_uri()
    SQLALCHEMY_ENGINE_OPTIONS = build_engine_options()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-secret")
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
    CORS_ORIGINS = get_cors_origins()
