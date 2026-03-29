"""
Async logging module with rotation, compression, and retention.

- Async logging via QueueHandler/QueueListener
- Rotation modes: 'none', 'size', 'time'
- Compression: zstd (.zst), fallback to gzip (.gz) if zstd missing
- Retention: keep only N (0..10)most recent rotated files
- `backup_count=0` disables rotation (no `.1.zst` created)
- `compress=True` → requires `log_file`, else raises ValueError
"""

import os
import queue
import logging
import threading
import gzip
import shutil
import datetime as dt
import time
from typing import Optional, Literal, Union, List, Any, cast
from logging.handlers import (
    QueueHandler,
    QueueListener,
    RotatingFileHandler,
    TimedRotatingFileHandler,
)

zstd: Any = None
try:
    import compression.zstd as zstd  # type: ignore[assignment]
    _HAS_ZSTD = True
except ImportError:
    _HAS_ZSTD = False


class DuplicateFilter(logging.Filter):
    """Thread-safe duplicate filter (level + message only, max 10)."""

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._logged = set()

    def filter(self, record: logging.LogRecord) -> bool:
        entry = (record.levelno, record.getMessage())
        with self._lock:
            if entry in self._logged:
                return False
            self._logged.add(entry)
            if len(self._logged) > 10:
                self._logged.clear()
        return True


def compress_file(src: str, dst: str) -> None:
    """Compress src to dst using zstd or gzip."""
    if _HAS_ZSTD and zstd is not None:
        with open(src, "rb") as f_in, zstd.open(dst, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        os.remove(src)
    else:
        gz = dst + ".gz"
        with open(src, "rb") as f_in, gzip.open(gz, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        os.remove(src)


class CompressingRotatingFileHandler(RotatingFileHandler):
    """Size-based handler with compression, backup_count[0..10], no rotation if backup_count=0."""

    def __init__(
        self,
        filename: str,
        mode: str = "a",
        maxBytes: int = 0,
        backupCount: int = 5,
        compress: bool = True,
        encoding: Optional[str] = "utf-8",
        delay: bool = False,
    ):
        if not (0 <= backupCount <= 10):
            raise ValueError(f"backupCount={backupCount} must be 0–10")
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
        self._compress = compress
        self._base = filename

    def shouldRollover(self, record) -> bool:
        if self.backupCount == 0:
            return False
        return bool(super().shouldRollover(record))

    def doRollover(self) -> None:
        if self.stream:
            self.stream.close()
            cast(Any, self).stream = None

        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                src = f"{self._base}.{i}"
                if self._compress:
                    src += ".zst"
                dst = f"{self._base}.{i + 1}"
                if self._compress:
                    dst += ".zst"
                if os.path.exists(src):
                    os.rename(src, dst)

            # Rename current file to .1, then compress
            if os.path.exists(self.baseFilename):
                # First rename to .1 without compression extension
                temp_dst = f"{self._base}.1"
                os.rename(self.baseFilename, temp_dst)

                # Then compress if needed
                if self._compress:
                    compress_file(temp_dst, temp_dst + ".zst")

            if not self.delay:
                self.stream = self._open()

    def _open(self):
        return open(self.baseFilename, "a", encoding=self.encoding or "utf-8")


class CompressingTimedRotatingFileHandler(TimedRotatingFileHandler):
    """Time-based handler with compression and backup_count ≤ 10."""

    def __init__(
        self,
        filename: str,
        when: str = "H",
        interval: int = 1,
        backupCount: int = 5,
        compress: bool = True,
        encoding: Optional[str] = "utf-8",
        delay: bool = False,
        utc: bool = False,
        atTime: Optional[dt.time] = None,
    ):
        if not (0 <= backupCount <= 10):
            raise ValueError(f"backupCount={backupCount} must be 0–10")
        super().__init__(filename, when, interval, backupCount, encoding, delay, utc, atTime)
        self._compress = compress
        self._base = filename

    def shouldRollover(self, record) -> bool:
        if self.backupCount == 0:
            return False
        return bool(super().shouldRollover(record))

    def doRollover(self) -> None:
        if self.stream:
            self.stream.close()
            cast(Any, self).stream = None

        if self.backupCount > 0:
            # Renumber existing rotated files
            for i in range(self.backupCount, 1, -1):
                src = f"{self._base}.{i}.zst"
                dst = f"{self._base}.{i - 1}.zst"
                if os.path.exists(src):
                    os.rename(src, dst)

            dst = f"{self._base}.1.zst"
            if os.path.exists(self.baseFilename):
                os.rename(self.baseFilename, dst)
                if self._compress:
                    compress_file(dst, dst)

            if not self.delay:
                self.stream = self._open()

        # Cleanup beyond backupCount
        for i in range(self.backupCount + 1, 20):
            path = f"{self._base}.{i}.zst"
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            else:
                break

    def _open(self):
        return open(self.baseFilename, "a", encoding=self.encoding or "utf-8")


def logger(
    name: str,
    level: Union[str, int] = "INFO",
    log_file: Optional[str] = None,
    rotation: Literal["none", "size", "time"] = "none",
    max_bytes: int = 5_000_000,
    when: str = "H",
    interval: int = 1,
    backup_count: int = 5,
    compress: bool = False,
) -> logging.Logger:
    """Create async logger with optional rotation, compression, and retention."""
    if compress and log_file is None:
        raise ValueError("compress=True requires log_file to be specified")
    if not (0 <= backup_count <= 10):
        raise ValueError(f"backup_count={backup_count} must be 0–10")

    level_val = level if isinstance(level, int) else getattr(logging, level.upper(), logging.INFO)
    logger_obj = logging.getLogger(name)
    logger_any = cast(Any, logger_obj)

    # If logger already has handlers and was created by aqdlog, update its level and return
    if logger_obj.hasHandlers() and hasattr(logger_obj, "queue_listener"):
        logger_obj.setLevel(level_val)
        # Ensure shutdown method exists
        if not hasattr(logger_obj, "shutdown"):
            # Try to get the existing listener and handlers
            if hasattr(logger_obj, "queue_listener") and hasattr(logger_obj, "_aqdlog_queue_handler"):
                listener = logger_any.queue_listener
                queue_handler = logger_any._aqdlog_queue_handler
                handlers = logger_obj.handlers

                def shutdown():
                    listener.stop()
                    for h in handlers:
                        h.close()
                    logger_obj.removeHandler(queue_handler)

                logger_any.shutdown = shutdown
        return logger_obj

    # If logger exists but doesn't have handlers (e.g., from previous test), recreate it
    if logger_obj.hasHandlers():
        # Clear existing handlers
        for h in logger_obj.handlers[:]:
            logger_obj.removeHandler(h)

    log_queue = queue.Queue(-1)
    queue_handler = QueueHandler(log_queue)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s:%(funcName)s:%(lineno)s - %(message)s"
    )
    queue_handler.setFormatter(formatter)
    logger_obj.setLevel(level_val)
    logger_obj.addHandler(queue_handler)

    logger_obj.addFilter(DuplicateFilter())

    handlers: List[logging.Handler] = []
    if log_file:
        if rotation == "none":
            handlers.append(logging.FileHandler(log_file))
        elif rotation == "size":
            handlers.append(
                CompressingRotatingFileHandler(
                    log_file, maxBytes=max_bytes, backupCount=backup_count, compress=compress
                )
            )
        elif rotation == "time":
            handlers.append(
                CompressingTimedRotatingFileHandler(
                    log_file, when=when, interval=interval, backupCount=backup_count, compress=compress
                )
            )
        else:
            raise ValueError(f"rotation={rotation!r} must be 'none','size','time'")
    else:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        handlers.append(console)

    listener = QueueListener(log_queue, *handlers)
    listener.start()
    logger_any.queue_listener = listener
    logger_any._aqdlog_queue_handler = queue_handler

    def shutdown():
        listener.stop()
        for h in handlers:
            h.close()
        logger_obj.removeHandler(queue_handler)

    logger_any.shutdown = shutdown
    return logger_obj


__all__ = ["logger"]
