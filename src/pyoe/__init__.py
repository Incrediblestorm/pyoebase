"""pyoe – Python utilities for Progress OpenEdge schema management.

Quick start::

    from pyoe.db import create_empty_db
    from pyoe.schema import dump_schema, parse_df, sync_schema

    # Create an empty database
    create_empty_db("/var/db/myapp")

    # Dump its schema to a .df file
    dump_schema("/var/db/myapp", "/tmp/myapp.df")

    # Parse the .df into Python objects
    schema = parse_df("/tmp/myapp.df")
    for table in schema.tables.values():
        print(table.name, list(table.fields.keys()))

    # Alter a database to match a .df file
    sync_schema("/var/db/myapp", "/tmp/desired_schema.df")
"""

from .exceptions import (
    OEConfigError,
    OEDBAlreadyExistsError,
    OEDBNotFoundError,
    OEError,
    OERuntimeError,
    OESchemaError,
)
from .sync import SyncResult, print_progress, sync_many

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "OEError",
    "OERuntimeError",
    "OEDBNotFoundError",
    "OEDBAlreadyExistsError",
    "OESchemaError",
    "OEConfigError",
    "SyncResult",
    "sync_many",
    "print_progress",
]
