import json
import pathlib
from datetime import datetime, timedelta, timezone

from app.utils.logger import get_logger

log = get_logger(__name__)

SEEDS_DIR = pathlib.Path(__file__).parent.parent.parent / "seeds"


def seed_plugins(db) -> None:
    from app.models.plugin import Plugin

    plugin_dir = SEEDS_DIR / "plugins"
    if not plugin_dir.exists():
        log.warning("Seed directory not found: %s", plugin_dir)
        return

    now = datetime.now(timezone.utc)

    # Built-in plugins are the source of truth in seed files; wipe and reinsert on every boot.
    # User-created plugins (is_builtin=False) are preserved.
    db.query(Plugin).filter(Plugin.is_builtin == True).delete(synchronize_session=False)

    inserted = 0
    for f in sorted(plugin_dir.rglob("*.json")):
        try:
            data = json.loads(f.read_text())
        except Exception as e:
            log.error("Failed to parse seed file %s: %s", f.name, e)
            continue

        plugin = Plugin(
            name=data["name"],
            db=data.get("db", ""),
            type=data["type"],
            format=data["format"],
            description=data.get("description", ""),
            config=json.dumps(data["config"]),
            is_builtin=True,
            created_at=now,
            updated_at=now,
        )
        db.add(plugin)
        inserted += 1

    db.commit()
    log.info("Seeded %d built-in plugins", inserted)
