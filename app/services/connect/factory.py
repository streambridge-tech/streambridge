from app.services.connect.backend import DeploymentBackend
from app.services.connect.kubernetes_backend import KubernetesBackend
from app.services.connect.rest_backend import RestBackend


def deployment_of(kc_config: dict | None) -> str:
    """Return ``kubernetes`` or ``connect``.

    ``deployment`` is the stored field. Older rows used ``mode: rest`` for Connect
    and ``mode: kubernetes`` for Strimzi. A missing value stays Connect.
    """
    cfg = kc_config or {}
    raw = str(cfg.get("deployment") or "").strip().lower()
    if raw in ("kubernetes", "connect"):
        return raw
    if str(cfg.get("mode") or "").strip().lower() == "kubernetes":
        return "kubernetes"
    return "connect"


def get_backend(kc_config: dict) -> DeploymentBackend:
    """Pick a Kafka Connect backend from the kafka_connect connection config."""
    if deployment_of(kc_config) == "kubernetes":
        return KubernetesBackend(kc_config)
    return RestBackend(kc_config)
