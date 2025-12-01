# aqdlog (aqdlog)

Asynchronous logging helper for Python providing:

* Non-blocking logging via QueueHandler + QueueListener
* Simple deduplication of repeated (level, message) pairs
* Timestamp / level / function / line formatting
* Optional file output (console by default)

## Installation

Using uv (recommended):
```bash
uv add aqdlog
```

Standard pip (after publishing):
```bash
pip install aqdlog
```

## Quick Start
```python
from aqdlog import log

logger = log("my_app", level="INFO")
logger.info("Service start")
logger.warning("Low disk space")
logger.warning("Low disk space")  # Duplicate suppressed
```

## API
```python
log(name: str, level: str = "INFO", log_file: str | None = None) -> logging.Logger
```
Args:
* name: Logger name (use __name__)
* level: Case-insensitive level name (INFO/DEBUG/WARNING/ERROR/CRITICAL)
* log_file: File path; omit for stderr

Returns a Logger configured with QueueHandler and a running QueueListener.

### Deduplication
DuplicateFilter remembers (level, message) pairs; repeats are dropped for the lifetime of the logger instance. Structured extras are ignored.

### Shutdown
Implementation currently assigns `logger.shutdown = shutdown()` (invoked immediately). Prefer `logging.shutdown()` on process exit to flush handlers.

## Limitations
* Unlimited queue size (-1)
* Naive duplicate suppression
* Re-calling log() with same name returns existing logger; later level/file changes ignored

## Roadmap
Configurable dedup strategy, max queue size, dynamic reconfiguration, graceful listener stop, structured logging.

## License
MIT
