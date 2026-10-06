import importlib
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool
from app.utils.config import get_database_url
from app.utils.logger import get_logger

log = get_logger(__name__)

# ── Driver availability check ─────────────────────────────────────────────────

_DRIVER_HINTS = {
    "postgresql": ("psycopg2", "uv add psycopg2-binary"),
    "mysql":      ("pymysql",  "uv add pymysql"),
}

def _check_driver(url: str):
    for backend, (module, install_hint) in _DRIVER_HINTS.items():
        if backend in url:
            try:
                importlib.import_module(module)
            except ImportError:
                raise RuntimeError(
                    f"Driver '{module}' not installed for {backend}. "
                    f"Run: {install_hint}"
                )

# ── Engine setup ──────────────────────────────────────────────────────────────

DATABASE_URL = get_database_url()
_check_driver(DATABASE_URL)

_sqlite = DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _sqlite else {}

# SQLite keeps a pooled connection's file handle. Replacing the database file
# on disk then makes later writes fail as readonly. NullPool opens the file
# for each session, so the next request sees the current file.
_engine_kwargs = {
    "connect_args": _connect_args,
    "echo": False,
    "pool_pre_ping": not _sqlite,
}
if _sqlite:
    _engine_kwargs["poolclass"] = NullPool
engine = create_engine(DATABASE_URL, **_engine_kwargs)


@event.listens_for(engine, "handle_error")
def _drop_readonly_connection(context):
    orig = context.original_exception
    if orig is not None and "readonly database" in str(orig).lower():
        engine.dispose()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def reopen_db() -> None:
    """Drop pooled connections so the next session opens the database file again.

    SQLite keeps the original file handle. Replacing the file on disk, which git
    does when it stashes the database, makes later writes fail as readonly.
    """
    engine.dispose()
    log.warning("Database connections closed so the next session reopens the file")


# ── Base model ────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Init ──────────────────────────────────────────────────────────────────────

def init_db():
    from app.models import connection, plugin, pipeline, connector_config, vault, alert  # noqa: F401
    from app.models import alert_delivery_attempt  # noqa: F401
    from app.models import connector_notebook, connector_command_log, connector_folder  # noqa: F401
    from app.models import user  # noqa: F401
    from app.models import role  # noqa: F401
    from app.models import workspace  # noqa: F401
    from app.models import audit  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _ensure_alert_columns()
    _ensure_delivery_columns()
    _ensure_user_columns()
    _ensure_notebook_columns()

    # verify connection is actually reachable
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    backend = DATABASE_URL.split(":")[0].split("+")[0]
    log.info("Database ready  backend=%s  url=%s", backend, _safe_url(DATABASE_URL))


def _ensure_alert_columns():
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(engine)
    if "alerts" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("alerts")}
    stmts = []
    if "active" not in existing:
        stmts.append("ALTER TABLE alerts ADD COLUMN active BOOLEAN NOT NULL DEFAULT 1")
    if "check_every_min" not in existing:
        stmts.append("ALTER TABLE alerts ADD COLUMN check_every_min INTEGER NOT NULL DEFAULT 5")
    if "match_action" not in existing:
        stmts.append("ALTER TABLE alerts ADD COLUMN match_action VARCHAR(16) NOT NULL DEFAULT 'pause'")
    added_rules = False
    if "rules_json" not in existing:
        stmts.append("ALTER TABLE alerts ADD COLUMN rules_json TEXT")
        added_rules = True
    if "notebook_id" not in existing:
        stmts.append("ALTER TABLE alerts ADD COLUMN notebook_id VARCHAR(36)")
    if not stmts:
        return
    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))
        if added_rules:
            conn.execute(text("UPDATE alerts SET rules_json = '[]' WHERE rules_json IS NULL"))


def _ensure_user_columns():
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(engine)
    if "users" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("users")}
    if "default_role_id" in existing:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN default_role_id INTEGER"))


def _ensure_notebook_columns():
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(engine)
    if "connector_notebooks" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("connector_notebooks")}
    stmts = []
    if "live_state" not in existing:
        stmts.append("ALTER TABLE connector_notebooks ADD COLUMN live_state VARCHAR(16) NOT NULL DEFAULT ''")
    if "live_tasks" not in existing:
        stmts.append("ALTER TABLE connector_notebooks ADD COLUMN live_tasks VARCHAR(16)")
    if "live_checked_at" not in existing:
        stmts.append("ALTER TABLE connector_notebooks ADD COLUMN live_checked_at DATETIME")
    if not stmts:
        return
    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))


def _ensure_delivery_columns():
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(engine)
    if "alert_delivery_attempts" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("alert_delivery_attempts")}
    stmts = []
    if "status" not in existing:
        stmts.append("ALTER TABLE alert_delivery_attempts ADD COLUMN status VARCHAR(32)")
    if "message" not in existing:
        stmts.append("ALTER TABLE alert_delivery_attempts ADD COLUMN message VARCHAR(2000)")
    if "log_text" not in existing:
        stmts.append("ALTER TABLE alert_delivery_attempts ADD COLUMN log_text TEXT")
    if not stmts:
        return
    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))


def _safe_url(url: str) -> str:
    """Mask password in the URL for safe logging."""
    from urllib.parse import urlparse, urlunparse
    try:
        p = urlparse(url)
        if p.password:
            masked = p._replace(netloc=p.netloc.replace(p.password, "****"))
            return urlunparse(masked)
    except Exception:
        pass
    return url


# ── Session dependency ────────────────────────────────────────────────────────

def get_db():
    """Return a session that the caller must close. Use as: db = get_db(); ...; db.close()"""
    return SessionLocal()
