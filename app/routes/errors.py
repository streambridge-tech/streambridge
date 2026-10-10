"""JSON error responses for /api/ routes. Pages keep Flask's HTML error pages."""

import json

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from app.utils.logger import get_logger

log = get_logger(__name__)


def _is_api() -> bool:
    return request.path.startswith("/api/")


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def http_error(exc: HTTPException):
        if not _is_api() or exc.response is not None:
            return exc
        response = exc.get_response()  # keeps headers such as Allow on a 405
        response.data = json.dumps({"error": exc.description})
        response.content_type = "application/json"
        return response

    @app.errorhandler(Exception)
    def unhandled_error(exc: Exception):
        if not _is_api():
            raise exc  # Flask's own handling: HTML 500, or the debugger when propagating
        log.exception("Unhandled error on %s %s", request.method, request.path)
        return jsonify({"error": "Internal server error"}), 500
