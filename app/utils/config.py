import os
import pathlib
from urllib.parse import quote_plus

import yaml

ROOT = pathlib.Path(__file__).parent.parent.parent
STATIC_DIR = ROOT / "static"
DIST_DIR = STATIC_DIR / "dist"

_profile_path = ROOT / "profile.yaml"
_profile: dict = yaml.safe_load(_profile_path.read_text()) if _profile_path.exists() else {}

ENV_PREFIX = "STREAMBRIDGE"


def _load_dotenv(path: pathlib.Path | None = None) -> None:
    """Load KEY=value lines from .env. A variable already set in the shell wins."""
    env_path = path or (ROOT / ".env")
    if not env_path.is_file():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


_load_dotenv()


def _env(*keys: str) -> str | None:
    """Read STREAMBRIDGE__SECTION__KEY from environment."""
    key = "__".join([ENV_PREFIX] + [k.upper() for k in keys])
    return os.environ.get(key)


def _get(section: str, key: str, default=None):
    return _profile.get(section, {}).get(key, default)


def _get_nested(section: str, subsection: str, key: str, default=None):
    return _profile.get(section, {}).get(subsection, {}).get(key, default)


def _present(value) -> bool:
    if value is None:
        return False
    return bool(str(value).strip())


def _as_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _as_list(value) -> list[str]:
    """A yaml list, or a comma-separated string from the environment."""
    items = value.split(",") if isinstance(value, str) else (value or [])
    return [str(item).strip() for item in items if str(item).strip()]


def _prefer(file_value, env_value, default=""):
    """Use the yaml value when it is set. Otherwise use the environment."""
    if _present(file_value):
        return file_value
    if _present(env_value):
        return env_value
    return default


def get_database_url() -> str:
    """
    Resolve the internal database URL.

    A value set in profile.yaml is used. When that field is missing or blank,
    the matching STREAMBRIDGE__DATABASE__* environment variable is used.
    """
    backend = str(_prefer(
        _get("database", "backend"),
        _env("database", "backend"),
        "sqlite",
    )).lower()

    if backend == "sqlite":
        path = _prefer(
            _get_nested("database", "sqlite", "path"),
            _env("database", "sqlite", "path"),
            "data/streambridge.db",
        )
        resolved = pathlib.Path(str(path))
        if not resolved.is_absolute():
            resolved = ROOT / resolved
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{resolved}"

    if backend == "postgresql":
        host = _prefer(_get_nested("database", "postgresql", "host"), _env("database", "postgresql", "host"), "localhost")
        port = _prefer(_get_nested("database", "postgresql", "port"), _env("database", "postgresql", "port"), 5432)
        database = _prefer(_get_nested("database", "postgresql", "database"), _env("database", "postgresql", "database"), "streambridge")
        username = _prefer(_get_nested("database", "postgresql", "username"), _env("database", "postgresql", "username"), "postgres")
        password = _prefer(_get_nested("database", "postgresql", "password"), _env("database", "postgresql", "password"), "")
        return (
            f"postgresql+psycopg2://{quote_plus(str(username))}:{quote_plus(str(password))}"
            f"@{host}:{port}/{database}"
        )

    if backend == "mysql":
        host = _prefer(_get_nested("database", "mysql", "host"), _env("database", "mysql", "host"), "localhost")
        port = _prefer(_get_nested("database", "mysql", "port"), _env("database", "mysql", "port"), 3306)
        database = _prefer(_get_nested("database", "mysql", "database"), _env("database", "mysql", "database"), "streambridge")
        username = _prefer(_get_nested("database", "mysql", "username"), _env("database", "mysql", "username"), "root")
        password = _prefer(_get_nested("database", "mysql", "password"), _env("database", "mysql", "password"), "")
        return (
            f"mysql+pymysql://{quote_plus(str(username))}:{quote_plus(str(password))}"
            f"@{host}:{port}/{database}"
        )

    raise ValueError(f"Unsupported database backend: '{backend}'. Choose sqlite | postgresql | mysql")


class Config:
    # Debug turns on the Werkzeug debugger, which runs code typed into an error page.
    DEBUG: bool = _as_bool(_prefer(_get("server", "debug"), _env("server", "debug"), False))
    TESTING = False

    APP_NAME: str    = _get("app", "name", "StreamBridge")
    APP_VERSION: str = _get("app", "version", "0.1.0")

    SERVER_HOST: str = _get("server", "host", "127.0.0.1")
    SERVER_PORT: int = _get("server", "port", 5000)
    # Extra Host names a personal-mode server answers to (loopback is always allowed).
    SERVER_ALLOWED_HOSTS: list[str] = _as_list(_get("server", "allowed_hosts") or _env("server", "allowed_hosts"))

    KAFKA_BOOTSTRAP_SERVERS: str = _get("kafka", "bootstrap_servers", "localhost:9092")
    KAFKA_CONNECT_URL: str       = _get("kafka_connect", "url", "http://localhost:8083")

    LOG_LEVEL: str  = _get("logging", "level", "INFO")
    LOG_FORMAT: str = _get("logging", "format", "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")

    AUTH_ENABLED: bool = _as_bool(_prefer(_get("auth", "enabled"), _env("auth", "enabled"), False))
    AUTH_SECRET_KEY: str = _prefer(_get("auth", "secret_key"), _env("auth", "secret_key"), "")
    AUTH_SESSION_LIFETIME_MIN: int = int(_prefer(_get("auth", "session_lifetime_min"), _env("auth", "session_lifetime_min"), 720))
    AUTH_COOKIE_SECURE: bool = _as_bool(_prefer(_get("auth", "cookie_secure"), _env("auth", "cookie_secure"), False))


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


configs = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "default":     Config,
}


def get_config():
    env = os.getenv("FLASK_ENV", "default")
    return configs.get(env, Config)
