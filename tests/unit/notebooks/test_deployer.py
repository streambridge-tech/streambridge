import unittest
from types import SimpleNamespace

from app.services.notebooks.deployer import NotebookDeployError, NotebookDeployer
from app.services.notebooks.secrets import SecretResolver
from app.services.notebooks.validator import NotebookValidator
from app.models.connector_notebook import ConnectorNotebook


class FakeVault:
    def __init__(self, name, vars_):
        self.name = name
        self.vars = vars_


class FakeQuery:
    def __init__(self, db, model):
        self.db = db
        self.model = model

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        if self.model.__name__ == "Connection":
            return self.db.connection
        return None

    def all(self):
        if self.model.__name__ == "Vault":
            return self.db.vaults
        return []


class FakeDB:
    def __init__(self, connection=None, vaults=None):
        self.connection = connection
        self.vaults = vaults or []
        self.added = []

    def query(self, model):
        return FakeQuery(self, model)

    def add(self, row):
        self.added.append(row)

    def flush(self):
        pass


class FakeBackend:
    def __init__(self, state="RUNNING", error=None, validate_report=None, validate_error=None):
        self.state = state
        self.error = error
        self.deploys = []
        self.validates = []
        self.validate_report = validate_report or {"error_count": 0, "configs": []}
        self.validate_error = validate_error

    def deploy(self, name, config):
        self.deploys.append((name, dict(config)))
        if self.error:
            raise RuntimeError(self.error)

    def poll_status(self, name):
        return self.state

    def validate_config(self, plugin_class, config, connector_name=None):
        body = dict(config)
        if connector_name and not body.get("name"):
            body["name"] = connector_name
        self.validates.append((plugin_class, body))
        if self.validate_error:
            raise RuntimeError(self.validate_error)
        return self.validate_report


class TestSecretResolver(unittest.TestCase):
    def test_resolves_token_and_redacts_password_key(self):
        vaults = [FakeVault("prod", [{"key": "DB_PASSWORD", "value": "s3cret", "masked": True}])]
        resolver = SecretResolver(vaults)
        resolved, missing, refs = resolver.resolve_config({
            "database.password": "{prod.DB_PASSWORD}",
            "database.user": "dbz",
        })
        self.assertEqual(missing, [])
        self.assertEqual(refs, 1)
        self.assertEqual(resolved["database.password"], "s3cret")
        redacted = resolver.redact_config(resolved)
        self.assertEqual(redacted["database.password"], "••••••••")
        self.assertEqual(redacted["database.user"], "dbz")

    def test_missing_secret(self):
        resolver = SecretResolver([])
        _resolved, missing, _refs = resolver.resolve_config({"database.password": "{prod.DB_PASSWORD}"})
        self.assertEqual(missing, ["prod.DB_PASSWORD"])


class TestNotebookDeployer(unittest.TestCase):
    def _notebook(self, **kwargs):
        n = ConnectorNotebook(
            id="nb-1",
            name="pg-src",
            attached_cluster="kc",
            doc_json='{"name":"pg-src","config":{"connector.class":"io.debezium.connector.postgresql.PostgresConnector","database.password":"{prod.DB_PASSWORD}"}}',
        )
        for k, v in kwargs.items():
            setattr(n, k, v)
        return n

    def test_happy_path_logs_three_ok_steps(self):
        conn = SimpleNamespace(name="kc", type="connect", subtype="kafka-connect", config={"url": "http://kc"})
        vaults = [FakeVault("prod", [{"key": "DB_PASSWORD", "value": "s3cret", "masked": True}])]
        db = FakeDB(conn, vaults)
        backend = FakeBackend("RUNNING")
        deployer = NotebookDeployer(db, get_backend_fn=lambda _c: backend, sleep=lambda _s: None, poll_timeout=0, poll_interval=0)
        result = deployer.deploy(self._notebook())
        self.assertEqual(result["status"], "success")
        self.assertEqual(backend.deploys[0][1]["database.password"], "s3cret")
        steps = [(r.step, r.status) for r in db.added]
        self.assertEqual(steps, [
            ("save_config", "ok"),
            ("resolve_secrets", "ok"),
            ("deploy_connector", "ok"),
        ])
        self.assertTrue(all("s3cret" not in (r.detail or "") for r in db.added))

    def test_missing_secret_stops_before_connect(self):
        conn = SimpleNamespace(name="kc", type="connect", subtype="kafka-connect", config={"url": "http://kc"})
        db = FakeDB(conn, [])
        backend = FakeBackend("RUNNING")
        deployer = NotebookDeployer(db, get_backend_fn=lambda _c: backend, sleep=lambda _s: None, poll_timeout=0, poll_interval=0)
        with self.assertRaises(NotebookDeployError) as ctx:
            deployer.deploy(self._notebook())
        self.assertEqual(ctx.exception.step, "resolve_secrets")
        self.assertEqual(backend.deploys, [])

    def test_connect_failure_marks_failed(self):
        conn = SimpleNamespace(name="kc", type="connect", subtype="kafka-connect", config={"url": "http://kc"})
        vaults = [FakeVault("prod", [{"key": "DB_PASSWORD", "value": "s3cret", "masked": True}])]
        db = FakeDB(conn, vaults)
        backend = FakeBackend(error="worker down")
        notebook = self._notebook()
        deployer = NotebookDeployer(db, get_backend_fn=lambda _c: backend, sleep=lambda _s: None, poll_timeout=0, poll_interval=0)
        with self.assertRaises(NotebookDeployError):
            deployer.deploy(notebook)
        self.assertEqual(notebook.last_deploy_status, "failed")
        self.assertIn("worker down", notebook.last_deploy_error)


class TestNotebookValidator(unittest.TestCase):
    def _notebook(self):
        return ConnectorNotebook(
            id="nb-1",
            name="pg-src",
            attached_cluster="kc",
            doc_json='{"name":"pg-src","config":{"connector.class":"io.debezium.connector.postgresql.PostgresConnector","database.password":"{prod.DB_PASSWORD}"}}',
        )

    def test_kc_field_errors_block_ok(self):
        conn = SimpleNamespace(name="kc", type="connect", subtype="kafka-connect", config={"url": "http://kc"})
        vaults = [FakeVault("prod", [{"key": "DB_PASSWORD", "value": "s3cret", "masked": True}])]
        db = FakeDB(conn, vaults)
        report = {
            "error_count": 1,
            "configs": [{
                "value": {"name": "database.hostname", "value": "", "errors": ["may not be empty"]},
            }],
        }
        backend = FakeBackend(validate_report=report)
        result = NotebookValidator(db, get_backend_fn=lambda _c: backend).validate(self._notebook())
        self.assertFalse(result["ok"])
        self.assertTrue(any("database.hostname" in e for e in result["errors"]))
        self.assertEqual(backend.validates[0][1]["database.password"], "s3cret")
        self.assertEqual(backend.validates[0][1]["name"], "pg-src")
        self.assertTrue(all("s3cret" not in (row.detail or "") for row in db.added))

    def test_kc_accepts_config(self):
        conn = SimpleNamespace(name="kc", type="connect", subtype="kafka-connect", config={"url": "http://kc"})
        vaults = [FakeVault("prod", [{"key": "DB_PASSWORD", "value": "s3cret", "masked": True}])]
        db = FakeDB(conn, vaults)
        backend = FakeBackend()
        result = NotebookValidator(db, get_backend_fn=lambda _c: backend).validate(self._notebook())
        self.assertTrue(result["ok"])
        self.assertEqual(len(backend.validates), 1)
        self.assertEqual(backend.validates[0][1]["name"], "pg-src")

    def test_uses_wrapper_name_when_config_omits_name(self):
        conn = SimpleNamespace(name="kc", type="connect", subtype="kafka-connect", config={"url": "http://kc"})
        db = FakeDB(conn, [])
        backend = FakeBackend()
        notebook = ConnectorNotebook(
            id="nb-1",
            name="mysql-apicurio-002",
            attached_cluster="kc",
            doc_json='{"name":"mysql-apicurio-002","config":{"connector.class":"io.debezium.connector.mysql.MySqlConnector"}}',
        )
        result = NotebookValidator(db, get_backend_fn=lambda _c: backend).validate(notebook)
        self.assertTrue(result["ok"])
        self.assertEqual(backend.validates[0][1]["name"], "mysql-apicurio-002")
