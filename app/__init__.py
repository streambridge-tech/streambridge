from flask import Flask
from app.utils.config import get_config, STATIC_DIR
from app.utils.logger import get_logger
from app.utils.db import init_db

log = get_logger(__name__)


def create_app():
    app = Flask(__name__, static_folder=str(STATIC_DIR))
    app.config.from_object(get_config())
    log.info("Starting %s v%s", app.config["APP_NAME"], app.config["APP_VERSION"])
    from app.models import alert  # noqa: F401 — ensure table is registered before init_db
    from app.models import alert_delivery_attempt  # noqa: F401
    from app.models import vault  # noqa: F401
    from app.models import user  # noqa: F401
    init_db()

    from app.utils.db import SessionLocal
    from app.seeds.loader import seed_plugins
    from app.services.rbac.seed import seed_builtin_roles
    with SessionLocal() as _db:
        seed_plugins(_db)
        seed_builtin_roles(_db)

    from app.routes.pages import pages
    from app.routes.api import api
    from app.routes.auth_api import auth_api
    from app.routes.admin_api import admin_api
    from app.routes.connections_api import connections_api
    from app.routes.plugins_api import plugins_api
    from app.routes.pipelines_api import pipelines_api
    from app.routes.vaults_api import vaults_api
    from app.routes.alerts_api import alerts_api
    from app.routes.kafka_connect_api import kc_api
    from app.routes.schema_registry_api import schema_registry_api
    from app.routes.kafka_api import kafka_api
    from app.routes.notebooks_api import notebooks_api
    from app.routes.folders_api import folders_api

    app.register_blueprint(pages)
    app.register_blueprint(api)
    app.register_blueprint(auth_api)
    app.register_blueprint(admin_api)
    app.register_blueprint(connections_api)
    app.register_blueprint(plugins_api)
    app.register_blueprint(pipelines_api)
    app.register_blueprint(vaults_api)
    app.register_blueprint(alerts_api)
    app.register_blueprint(kc_api)
    app.register_blueprint(schema_registry_api)
    app.register_blueprint(kafka_api)
    app.register_blueprint(notebooks_api)
    app.register_blueprint(folders_api)

    from app.utils.auth import install_auth
    install_auth(app)

    from app.services.alerting.scheduler import start_alert_scheduler
    start_alert_scheduler(debug=app.debug)

    return app
