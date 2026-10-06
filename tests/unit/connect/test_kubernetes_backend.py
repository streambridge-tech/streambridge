"""Strimzi deploy path: manifest shape, backend selection, and the two API checks."""
import unittest
from unittest.mock import MagicMock, patch

from app.connectors.infra.kafka_connect import KafkaConnectConnector
from app.services.connect.factory import deployment_of, get_backend
from app.services.connect.kubernetes_backend import KubernetesBackend, connector_manifest
from app.services.connect.rest_backend import RestBackend


def _response(status, text=""):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    return resp


class TestDeploymentSelection(unittest.TestCase):

    def test_missing_deployment_stays_connect(self):
        self.assertEqual(deployment_of({}), "connect")
        self.assertIsInstance(get_backend({"url": "http://kc"}), RestBackend)

    def test_legacy_mode_kubernetes(self):
        self.assertEqual(deployment_of({"mode": "kubernetes"}), "kubernetes")
        self.assertIsInstance(get_backend({"mode": "kubernetes", "url": "http://kc"}), KubernetesBackend)

    def test_explicit_connect(self):
        self.assertEqual(deployment_of({"deployment": "connect", "mode": "kubernetes"}), "connect")


class TestConnectorManifest(unittest.TestCase):

    def test_lifts_class_and_tasks(self):
        body = connector_manifest("license-file", "my-connect-cluster", {
            "connector.class": "org.apache.kafka.connect.file.FileStreamSourceConnector",
            "tasks.max": "1",
            "file": "/opt/kafka/LICENSE",
            "topic": "license-topic",
        })
        self.assertEqual(body["metadata"]["name"], "license-file")
        self.assertEqual(body["metadata"]["labels"]["strimzi.io/cluster"], "my-connect-cluster")
        self.assertEqual(body["spec"]["class"], "org.apache.kafka.connect.file.FileStreamSourceConnector")
        self.assertEqual(body["spec"]["tasksMax"], 1)
        self.assertEqual(body["spec"]["config"]["topic"], "license-topic")
        self.assertNotIn("connector.class", body["spec"]["config"])
        self.assertNotIn("tasks.max", body["spec"]["config"])


class TestKubernetesDeploy(unittest.TestCase):

    def _backend(self):
        return KubernetesBackend({
            "url": "http://connect:8083",
            "api_host": "https://kube.example.com",
            "namespace": "kafka",
            "cluster": "my-connect-cluster",
            "api_token": "token-value",
        })

    @patch("app.services.connect.kubernetes_backend.requests.post")
    @patch("app.services.connect.kubernetes_backend.requests.get")
    def test_create_posts_the_connector(self, get, post):
        get.return_value = _response(404)
        post.return_value = _response(201)
        backend = self._backend()
        with patch.object(backend._rest, "_validate_or_raise"):
            backend.deploy("license-file", {
                "connector.class": "org.apache.kafka.connect.file.FileStreamSourceConnector",
                "tasks.max": "1",
                "topic": "license-topic",
            })
        self.assertIn("/namespaces/kafka/kafkaconnectors", post.call_args.args[0])
        sent = post.call_args.kwargs["json"]
        self.assertEqual(sent["metadata"]["labels"]["strimzi.io/cluster"], "my-connect-cluster")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer token-value")

    @patch("app.services.connect.kubernetes_backend.requests.patch")
    def test_pause_patches_state(self, patch_req):
        patch_req.return_value = _response(200)
        self._backend().pause("license-file")
        self.assertEqual(patch_req.call_args.kwargs["json"], {"spec": {"state": "paused"}})
        self.assertEqual(patch_req.call_args.kwargs["headers"]["Content-Type"], "application/merge-patch+json")


class TestConnectionChecks(unittest.TestCase):

    @patch("app.connectors.infra.kafka_connect.requests.get")
    def test_kubernetes_reports_forbidden_token(self, get):
        get.return_value = _response(403)
        result = KafkaConnectConnector().test_connection({
            "deployment": "kubernetes",
            "url": "http://connect:8083",
            "api_host": "https://kube.example.com",
            "namespace": "kafka",
            "cluster": "my-connect-cluster",
            "api_token": "token-value",
        })
        self.assertFalse(result["success"])
        self.assertIn("403", result["message"])

    def test_validate_requires_kubernetes_fields(self):
        errors = KafkaConnectConnector().validate({
            "url": "http://connect:8083",
            "deployment": "kubernetes",
        })
        self.assertTrue(any("api_host" in err for err in errors))
        self.assertTrue(any("api_token" in err for err in errors))
