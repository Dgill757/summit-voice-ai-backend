"""Custom exception types for domain and API layers."""


class AppError(Exception):
    """Base app exception."""


class ValidationError(AppError):
    """Validation failure for user input or generated artifacts."""


class IntegrationError(AppError):
    """External integration call failure."""


class BuilderDeploymentError(AppError):
    """AI builder deployment failure."""
