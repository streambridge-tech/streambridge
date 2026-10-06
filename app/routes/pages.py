from flask import Blueprint, redirect, send_from_directory
from app.utils.config import DIST_DIR

pages = Blueprint("pages", __name__)


@pages.get("/")
def index():
    return redirect("/connectors", 302)


@pages.get("/studio")
def studio():
    return redirect("/pipelines", 301)


@pages.get("/pipelines")
def pipelines():
    return send_from_directory(DIST_DIR, "pipelines.html")


@pages.get("/connections")
def connections():
    return send_from_directory(DIST_DIR, "connections.html")


@pages.get("/kafka-topics")
def kafka_topics():
    return send_from_directory(DIST_DIR, "kafka_topics.html")


@pages.get("/schema-registry")
def schema_registry():
    return send_from_directory(DIST_DIR, "schema_registry.html")


@pages.get("/connectors")
def connectors():
    return send_from_directory(DIST_DIR, "connectors.html")


@pages.get("/configs")
def configs():
    return redirect("/connectors", 301)


@pages.get("/docs")
def docs():
    return send_from_directory(DIST_DIR, "docs.html")


@pages.get("/rca")
def rca():
    return send_from_directory(DIST_DIR, "rca.html")


@pages.get("/plugins")
def plugins():
    return send_from_directory(DIST_DIR, "plugins.html")


@pages.get("/alerts")
def alerts():
    return send_from_directory(DIST_DIR, "alerts.html")


@pages.get("/admin")
def admin():
    return send_from_directory(DIST_DIR, "admin.html")
