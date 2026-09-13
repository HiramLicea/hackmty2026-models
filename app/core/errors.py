"""Domain and boundary errors translated by the HTTP layer."""

from app.models.common import ModelName


class InvalidApiKeyError(RuntimeError):
    """The caller did not present the configured server-to-server credential."""


class ServiceNotConfiguredError(RuntimeError):
    """A protected operation is unavailable because server configuration is incomplete."""


class ModelVersionMismatchError(RuntimeError):
    """An artifact does not match the service's supported model version."""

    def __init__(self, model_name: ModelName) -> None:
        super().__init__("model artifact version is incompatible")
        self.model_name = model_name
