from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified
from app.utils.db import SessionLocal
from app.models.vault import Vault
from app.utils.vaults import (
    collect_tokens,
    merge_vars,
    resolve_public,
    valid_vault_name,
    vaults_map,
)
from app.utils.logger import get_logger
from app.utils.auth import require

log = get_logger(__name__)
vaults_api = Blueprint("vaults_api", __name__, url_prefix="/api")


def _unique_name(db, raw: str) -> str:
    root = (raw or "").strip()
    if not valid_vault_name(root):
        return ""
    if not db.get(Vault, root):
        return root
    n = 2
    while db.get(Vault, f"{root}-{n}"):
        n += 1
    candidate = f"{root}-{n}"
    return candidate if valid_vault_name(candidate) else ""


@vaults_api.get("/secrets")
@vaults_api.get("/vaults")
@require("vault.read_refs")
def list_vaults():
    with SessionLocal() as db:
        rows = db.query(Vault).order_by(Vault.name).all()
        return jsonify([v.to_public_dict() for v in rows])


@vaults_api.get("/secrets/refs")
@vaults_api.get("/vaults/refs")
@require("vault.read_refs")
def list_refs():
    with SessionLocal() as db:
        out = []
        for vault in db.query(Vault).order_by(Vault.name).all():
            for row in vault.vars or []:
                key = str(row.get("key") or "").strip()
                if not key:
                    continue
                out.append({
                    "parent": vault.name,
                    "key": key,
                    "ref": f"{{{vault.name}.{key}}}",
                    "masked": bool(row.get("masked")),
                })
        return jsonify(out)


@vaults_api.post("/secrets/resolve")
@vaults_api.post("/vaults/resolve")
@require("vault.use_secrets")
def resolve_text():
    data = request.get_json(silent=True) or {}
    text = data.get("text")
    if not isinstance(text, str):
        return jsonify({"error": "text must be a string"}), 400
    with SessionLocal() as db:
        rows = db.query(Vault).all()
        result = resolve_public(text, vaults_map(rows))
        result["refs"] = collect_tokens(text)
        return jsonify(result)


@vaults_api.get("/secrets/<name>")
@vaults_api.get("/vaults/<name>")
@require("vault.read_refs")
def get_vault(name: str):
    with SessionLocal() as db:
        vault = db.get(Vault, name)
        if not vault:
            return jsonify({"error": f"Vault '{name}' not found"}), 404
        return jsonify(vault.to_public_dict())


@vaults_api.post("/secrets")
@vaults_api.post("/vaults")
@require("vault.create")
def create_vault():
    data = request.get_json(silent=True) or {}
    raw = (data.get("name") or "").strip()
    if not valid_vault_name(raw):
        return jsonify({"error": "name must start with a letter and use only letters, numbers, _ or -"}), 400
    with SessionLocal() as db:
        name = _unique_name(db, raw)
        if not name:
            return jsonify({"error": "Could not allocate a vault name"}), 400
        vault = Vault(name=name, vars=[])
        try:
            db.add(vault)
            db.commit()
            db.refresh(vault)
        except IntegrityError:
            db.rollback()
            return jsonify({"error": f"Vault '{raw}' already exists"}), 409
        log.info("Created vault '%s'", vault.name)
        return jsonify(vault.to_public_dict()), 201


@vaults_api.put("/secrets/<name>")
@vaults_api.put("/vaults/<name>")
@vaults_api.put("/vaults/<name>/vars")
@require("vault.add_secret")
def put_vars(name: str):
    data = request.get_json(silent=True) or {}
    incoming = data.get("vars")
    if not isinstance(incoming, list):
        return jsonify({"error": "vars must be a list"}), 400
    with SessionLocal() as db:
        vault = db.get(Vault, name)
        if not vault:
            return jsonify({"error": f"Vault '{name}' not found"}), 404
        merged, err = merge_vars(vault.vars or [], incoming)
        if err:
            return jsonify({"error": err}), 400
        vault.vars = list(merged)
        flag_modified(vault, "vars")
        db.commit()
        db.refresh(vault)
        log.info("Updated vault '%s' vars=%d", vault.name, len(merged))
        return jsonify(vault.to_public_dict())


@vaults_api.delete("/secrets/<name>")
@vaults_api.delete("/vaults/<name>")
@require("vault.delete")
def delete_vault(name: str):
    with SessionLocal() as db:
        vault = db.get(Vault, name)
        if not vault:
            return jsonify({"error": f"Vault '{name}' not found"}), 404
        leftover = [r for r in (vault.vars or []) if str(r.get("key") or "").strip()]
        if leftover:
            return jsonify({"error": "Remove all secrets from this bag before deleting it"}), 409
        db.delete(vault)
        db.commit()
        log.info("Deleted vault '%s'", name)
        return jsonify({"ok": True})
