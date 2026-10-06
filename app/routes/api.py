from flask import Blueprint, jsonify

from app.utils.logger import get_logger

log = get_logger(__name__)
api = Blueprint("api", __name__, url_prefix="/api")


@api.get("/health")
def health():
    return jsonify({"status": "ok"})
