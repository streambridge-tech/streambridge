from flask import Blueprint, jsonify, request

from app.models.connector_command_log import ConnectorCommandLog
from app.models.connector_folder import ConnectorFolder
from app.models.connector_notebook import ConnectorNotebook
from app.utils.db import SessionLocal
from app.utils.auth import require
from app.utils.logger import get_logger

log = get_logger("app.routes.folders")
folders_api = Blueprint("folders_api", __name__, url_prefix="/api/folders")


def clean_path(raw) -> str | None:
    text = str(raw or "").strip().replace("\\", "/")
    parts = []
    for part in text.split("/"):
        segment = part.strip().replace("/", "-")
        if not segment or segment in (".", ".."):
            return None
        parts.append(segment)
    if not parts:
        return None
    return "/".join(parts)[:256]


def _prefixes(path: str) -> list[str]:
    acc = ""
    out = []
    for part in path.split("/"):
        acc = f"{acc}/{part}" if acc else part
        out.append(acc)
    return out


def _matches(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def _moved(path: str, src: str, dest: str) -> str | None:
    if path == src:
        return dest
    if path.startswith(src + "/"):
        return dest + path[len(src):]
    return None


@folders_api.get("/")
@require("folder.read")
def list_folders():
    with SessionLocal() as db:
        rows = db.query(ConnectorFolder).order_by(ConnectorFolder.path).all()
        return jsonify([row.to_dict() for row in rows])


@folders_api.post("/")
@require("folder.create")
def create_folder():
    data = request.get_json(force=True) or {}
    path = clean_path(data.get("path") or data.get("name"))
    if not path:
        return jsonify({"error": "Folder name is required"}), 400
    with SessionLocal() as db:
        existing = {row.path for row in db.query(ConnectorFolder).all()}
        for prefix in _prefixes(path):
            if prefix in existing:
                continue
            db.add(ConnectorFolder(path=prefix))
            existing.add(prefix)
        db.commit()
        log.info("Folder created  path=%s", path)
        return jsonify({"path": path}), 201


@folders_api.patch("/")
@require("folder.rename")
def rename_folder():
    data = request.get_json(force=True) or {}
    src = clean_path(data.get("from") or data.get("path"))
    dest = clean_path(data.get("to"))
    if not src or not dest:
        return jsonify({"error": "Folder name is required"}), 400
    if src == dest:
        return jsonify({"path": dest})
    with SessionLocal() as db:
        folders = db.query(ConnectorFolder).all()
        notebooks = db.query(ConnectorNotebook).all()
        taken = {row.path for row in folders}
        for row in folders:
            moved = _moved(row.path, src, dest)
            if moved and moved != row.path:
                taken.discard(row.path)
        for row in list(folders):
            moved = _moved(row.path, src, dest)
            if not moved or moved == row.path:
                continue
            if moved in taken:
                return jsonify({"error": "A folder with that name already exists"}), 409
            taken.add(moved)
            db.delete(row)
            db.add(ConnectorFolder(path=moved))
        for notebook in notebooks:
            moved = _moved(notebook.folder or "", src, dest)
            if moved:
                notebook.folder = moved
        db.commit()
        log.info("Folder renamed  from=%s  to=%s", src, dest)
        return jsonify({"path": dest})


@folders_api.delete("/")
@require("folder.delete")
def delete_folder():
    data = request.get_json(silent=True) or {}
    path = clean_path(data.get("path") or request.args.get("path"))
    if not path:
        return jsonify({"error": "Folder name is required"}), 400
    with SessionLocal() as db:
        notebooks = [row for row in db.query(ConnectorNotebook).all() if _matches(row.folder or "", path)]
        for notebook in notebooks:
            db.query(ConnectorCommandLog).filter(ConnectorCommandLog.notebook_id == notebook.id).delete()
            db.delete(notebook)
        for row in db.query(ConnectorFolder).all():
            if _matches(row.path, path):
                db.delete(row)
        db.commit()
        log.info("Folder deleted  path=%s", path)
        return jsonify({"ok": True})
