"""Domain and boundary errors translated by the HTTP layer."""

from uuid import UUID

from app.models.common import ModelName


class InvalidApiKeyError(RuntimeError):
    """The caller did not present the configured server-to-server credential."""


class ServiceNotConfiguredError(RuntimeError):
    """A protected operation is unavailable because server configuration is incomplete."""


class UserNotFoundError(RuntimeError):
    """The verified user does not exist in the configured data source."""


class AccountNotFoundError(RuntimeError):
    """An account does not exist or is not owned by the verified user."""

    def __init__(self, account_id: UUID) -> None:
        super().__init__("account not found for verified user")
        self.account_id = account_id


class ModelVersionMismatchError(RuntimeError):
    """An artifact does not match the service's supported model version."""

    def __init__(self, model_name: ModelName) -> None:
        super().__init__("model artifact version is incompatible")
        self.model_name = model_name


class DataSourceUnavailableError(RuntimeError):
    """The configured financial data source cannot serve the request."""
