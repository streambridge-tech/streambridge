from abc import ABC, abstractmethod


class DeploymentBackend(ABC):
    """Backend for deploying a single Kafka Connect connector.

    Concrete backends: RestBackend (talks to Kafka Connect REST API),
    KubernetesBackend (applies Strimzi KafkaConnector CRD).
    """

    @abstractmethod
    def deploy(self, connector_name: str, config: dict) -> None:
        """Create or update the connector with the given config."""

    @abstractmethod
    def poll_status(self, connector_name: str) -> str:
        """Return the connector's current state: RUNNING | PAUSED | FAILED | PENDING | UNKNOWN."""

    @abstractmethod
    def exists(self, connector_name: str) -> bool:
        """Return True if the connector already exists at the target."""

    @abstractmethod
    def delete(self, connector_name: str) -> None:
        """Delete the connector at the target."""
