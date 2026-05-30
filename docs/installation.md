# Installation

## Requirements

| Requirement | Version |
|---|---|
| Python | 3.9 or later |
| Progress OpenEdge | 12.2.x (tested on 12.2.13) |
| Operating system | Linux (the OpenEdge runtime is Linux-only in this configuration) |

OpenEdge must be installed and the `DLC` environment variable must point to the installation root (typically `/usr/dlc`). All `pyoe` operations that call the OpenEdge runtime require this.

```bash
echo $DLC          # should print /usr/dlc or your install path
_progres --version # should print the OE version
```

---

## Installing pyoe

Clone or copy the repository, then install in editable mode:

```bash
cd /path/to/pyoe
pip install -e .
```

With development dependencies (pytest, coverage):

```bash
pip install -e ".[dev]"
```

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DLC` | Yes | `/usr/dlc` | Path to the OpenEdge installation directory |
| `PROPATH` | No | — | `pyoe` prepends `$DLC/tty` automatically; you do not need to set this |

You can override `DLC` per-call by passing `dlc=` to any function that accepts it:

```python
from pyoe.schema import sync_schema

sync_schema("/var/db/myapp", "/schemas/app.df", dlc="/opt/dlc-12.2.13")
```

---

## Verifying the installation

```python
import pyoe
print(pyoe.__version__)

from pyoe._oe import OERunner
runner = OERunner()          # raises OEConfigError if _progres is not found
print(runner.dlc)            # prints the DLC path being used
```

---

## Running the tests

Unit tests do not require a running OpenEdge installation — all subprocess calls are mocked:

```bash
pytest tests/unit/ -v
```

Integration tests connect to real databases and require OpenEdge and a copy of the `sports2000` sample database:

```bash
pytest -m integration -v
```

Skip integration tests explicitly:

```bash
pytest -m "not integration" -v
```
