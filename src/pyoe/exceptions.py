"""Exceptions for the pyoe package."""


class OEError(Exception):
    """Base exception for all OpenEdge errors."""


class OERuntimeError(OEError):
    """Raised when an OpenEdge batch process exits non-zero."""

    def __init__(self, message: str, returncode: int = 0, stderr: str = "", stdout: str = ""):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout


class OEDBNotFoundError(OEError):
    """Raised when a database file does not exist."""


class OEDBAlreadyExistsError(OEError):
    """Raised when trying to create a database that already exists."""


class OESchemaError(OEError):
    """Raised for schema parsing or application errors."""


class OEConfigError(OEError):
    """Raised for misconfiguration (e.g., DLC not found)."""
