"""Application configuration.

Development settings are the default. Production needs SECRET_KEY set
as an environment variable (see .env.example and README.md).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _database_url():
    url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith("postgres://"):  # some hosts still use the old prefix
        url = url.replace("postgres://", "postgresql://", 1)
    return url or None  # None -> app.py uses instance/events.db


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY") or None
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = True
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024
    SEED_SAMPLE_EVENTS = True


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # requires HTTPS


class TestingConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = "test-secret-key-not-for-real-use"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SEED_SAMPLE_EVENTS = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
