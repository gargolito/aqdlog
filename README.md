# aqdlog

`aqdlog` is a lightweight asynchronous logging helper for Python.

## Features

- Non-blocking logging via `QueueHandler` + `QueueListener`
- Duplicate suppression for repeated `(level, message)` pairs
- Optional file output with rotation modes:
	- `none`
	- `size`
	- `time`
- Optional compression for rotated files:
	- `.zst` when zstd is available
	- `.gz` fallback when zstd is unavailable
- Rotation retention via `backup_count` (`0..10`)
- Optional `silent` mode to disable console fallback and parent/root propagation
- Graceful logger shutdown via `logger.shutdown()`

## Installation

Using `uv`:

```bash
uv add aqdlog
```

Or with `pip`:

```bash
pip install aqdlog
```

## Quick start

```python
from aqdlog import logger

log = logger("my_app", level="INFO")
log.info("Service start")
log.warning("Low disk space")
log.warning("Low disk space")  # Duplicate suppressed
log.shutdown()
```

## API

```python
logger(
		name: str,
		level: str | int = "INFO",
		log_file: str | None = None,
		rotation: Literal["none", "size", "time"] = "none",
		max_bytes: int = 5_000_000,
		when: str = "H",
		interval: int = 1,
		backup_count: int = 5,
		compress: bool = False,
		silent: bool = False,
) -> logging.Logger
```

### Parameters

- `name`: Logger name (for example `__name__`)
- `level`: Logging level as string or integer
- `log_file`: Optional output file path; when omitted, logs go to console
- `rotation`: Rotation strategy (`none`, `size`, `time`)
- `max_bytes`: File size threshold for `size` rotation
- `when`: Time unit for `time` rotation (passed to `TimedRotatingFileHandler`)
- `interval`: Rotation interval for `time` rotation
- `backup_count`: Number of rotated files to keep (`0..10`)
- `compress`: Compress rotated files; requires `log_file`
- `silent`: Disable console fallback and stop propagation to parent/root loggers

### Validation rules

- `compress=True` requires `log_file`
- `backup_count` must be between `0` and `10` (inclusive)
- `backup_count=0` disables rollover

### File-only / journald-safe mode

Use `silent=True` when you want aqdlog to write only to its configured file handlers and not bubble records into parent or root loggers.

```python
from aqdlog import logger

log = logger(
	"my_service",
	log_file="/var/log/my_service.log",
	rotation="size",
	max_bytes=5_000_000,
	backup_count=3,
	compress=True,
	silent=True,
)

log.info("This goes to the log file only")
log.shutdown()
```

## Behavior notes

- Duplicate suppression is based on `(level, message)` only.
- Re-using the same logger name returns the same logger instance.
- The returned logger includes a `shutdown()` method that stops the queue listener and closes handlers.
- When `silent=True`, `logger.propagate` is set to `False`.

## Examples

Run the included example script:

```bash
uv run python examples/example_script.py
```

## License

MIT
