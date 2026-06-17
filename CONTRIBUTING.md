# Contributing to Datalens

Thank you for your interest in contributing to Datalens!

## Development Setup

```bash
# Clone the repository
git clone https://github.com/datalens-ai/datalens.git
cd datalens

# Install with dev dependencies using uv
uv sync --extra dev

# Run tests
uv run pytest

# Run linting
uv run ruff check src/
uv run mypy src/
```

## Adding a New Connector

Connectors are the extension point for supporting new data sources.

### 1. Create the Connector Module

Create `src/datalens/connectors/yourconnector.py`:

```python
from datalens.connectors.base import Connector, ObjectRef, Record
from typing import Iterator, Any

class YourConnector(Connector):
    """Connector for YourSource."""

    def connect(self) -> None:
        """Establish connection to the data source."""
        # Validate config, establish connection
        self._connected = True

    def list_objects(self) -> list[ObjectRef]:
        """Return list of available objects."""
        return [ObjectRef(name="object1"), ...]

    def sample(
        self,
        obj: ObjectRef,
        *,
        sample_size: int | None = None,
        max_depth: int | None = None,
    ) -> Iterator[Record]:
        """Yield sampled records from the object."""
        sample_size = sample_size or self.config.sample_size
        for record in self._fetch_records(obj, limit=sample_size):
            yield record

    def count(self, obj: ObjectRef) -> int | None:
        """Return total record count, or None if expensive."""
        return None  # Override if you can provide count efficiently

    def close(self) -> None:
        """Release resources."""
        self._connected = False
```

### 2. Register the Connector

Edit `src/datalens/connectors/registry.py`:

```python
def _register_builtins() -> None:
    from datalens.connectors.yourconnector import YourConnector
    register_connector("yoursource", YourConnector)
```

### 3. Add Tests

Create `tests/test_yourconnector.py` with unit tests.

### 4. Update Documentation

- Add CLI examples to README.md
- Document source-specific options

## Code Style

- Use `ruff` for linting and formatting
- Use `mypy` for type checking
- Follow existing code patterns
- Add docstrings to public APIs

## Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Ensure all tests pass and linting is clean
5. Submit a pull request with a clear description

## Questions?

Open an issue for discussion before major changes.
