#!/usr/bin/env python
# -*- coding: utf-8  -*-
"""
Unit tests for aqdlog.

Run: pytest test_aqdlog.py -v
"""

import os
import time
import tempfile
import logging
import builtins
import importlib
import sys
from pathlib import Path
import pytest
from aqdlog import logger, DuplicateFilter
from logging.handlers import QueueHandler


@pytest.fixture(autouse=True)
def cleanup_loggers():
    """Clean up loggers after each test to prevent caching issues."""
    yield
    # Remove all loggers created during the test
    for name in list(logging.Logger.manager.loggerDict.keys()):
        if name.startswith("test."):
            logging.getLogger(name).handlers.clear()
            logging.getLogger(name).level = logging.NOTSET


class TestDuplicateFilter:
    def test_dup_filter_reduces_duplicates(self):
        filter = DuplicateFilter()
        rec = type("Record", (), {})()
        rec.levelno = 20
        rec.getMessage = lambda: "Hello"

        assert filter.filter(rec) is True
        # Duplicate
        assert filter.filter(rec) is False
        # New message
        rec.getMessage = lambda: "World"
        assert filter.filter(rec) is True

    def test_dup_filter_clears_after_10(self):
        filter = DuplicateFilter()
        rec = type("Record", (), {})()
        rec.levelno = 20
        rec.getMessage = lambda: ""
        for i in range(12):
            rec.getMessage = lambda i=i: f"Msg{i}"
            filter.filter(rec)
        assert len([k for k, v in filter._logged]) <= 10


class TestBackwardCompatibility:
    def test_logger_defaults_to_console(self):
        # Use unique name to avoid cached logger
        log = logger("test.default.unique", level="INFO")
        assert log is not None
        assert log.level == logging.INFO  # INFO = 20
        # Console handler should be present (QueueHandler wraps the actual handler)
        assert any(isinstance(h, QueueHandler) for h in log.handlers)
        log.shutdown()


class TestRotationValidate:
    def test_compress_requires_logfile(self):
        with pytest.raises(ValueError, match="compress=True requires log_file"):
            logger("test", compress=True, log_file=None)

    def test_invalid_backup_count_low(self):
        with pytest.raises(ValueError, match="must be 0–10"):
            logger("test", backup_count=-1)

    def test_invalid_backup_count_high(self):
        with pytest.raises(ValueError, match="must be 0–10"):
            logger("test", backup_count=11)


class TestBackupZeroDisablesRotation:
    def test_backup_count_zero_disables_size_rotation(self):
        tmpdir = Path(tempfile.gettempdir()) / "test_backup_zero"
        tmpdir.mkdir(exist_ok=True)
        logfile = tmpdir / "zero.log"

        log = logger(
            "test.zero.unique",
            log_file=str(logfile),
            rotation="size",
            max_bytes=100,
            backup_count=0,
            compress=True,
        )

        for i in range(50):
            log.info(f"x{i:03d}-" + ("x" * 50))  # unique messages; >100 bytes total, should NOT rotate

        log.shutdown()

        files = list(tmpdir.glob("*.log*"))
        assert len(files) == 1
        assert files[0].name == "zero.log"

    def test_backup_count_zero_disables_time_rotation(self):
        tmpdir = Path(tempfile.gettempdir()) / "test_time_zero"
        tmpdir.mkdir(exist_ok=True)
        logfile = tmpdir / "time_zero.log"

        log = logger(
            "test.time_zero.unique",
            log_file=str(logfile),
            rotation="time",
            when="S",  # seconds (fast test)
            interval=1,
            backup_count=0,
            compress=True,
        )

        time.sleep(1.1)  # Force time rollover
        log.info("After rollover")
        log.shutdown()

        files = list(tmpdir.glob("*.log*"))
        assert len(files) == 1
        assert files[0].name == "time_zero.log"


class TestCompression:
    def test_zstd_compression_works(self, tmp_path):
        logfile = tmp_path / "comp.log"

        log = logger(
            "test.zstd.unique",
            log_file=str(logfile),
            rotation="size",
            max_bytes=100,
            backup_count=1,
            compress=True,
        )

        for i in range(10):
            log.info(f"zstd-{i:03d}-" + ("x" * 50))

        log.shutdown()

        files = sorted([f.name for f in tmp_path.glob("*.log*")])
        # After rollover: active 0.log, rotated 0.log.1.zst
        assert len(files) >= 2
        assert any(f.endswith(".zst") or f.endswith(".gz") for f in files)

    def test_gzip_fallback_works_when_zstd_missing(self, monkeypatch):
        # Remove zstandard from sys.modules to simulate missing package
        sys.modules.pop("zstandard", None)
        sys.modules.pop("compression.zstd", None)

        # Temporarily hide zstandard from import
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("compression.zstd") or name == "zstandard":
                raise ImportError("No module named 'zstandard'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        try:
            # Force re-import aqdlog
            for mod_name in list(sys.modules.keys()):
                if "aqdlog" in mod_name:
                    del sys.modules[mod_name]

            aqdlog = importlib.import_module("aqdlog")
            assert not aqdlog._HAS_ZSTD
            tmpdir = Path(tempfile.gettempdir()) / "test_gzip_fallback"
            tmpdir.mkdir(exist_ok=True)
            logfile = tmpdir / "gzip.log"
            log = aqdlog.logger(
                "test.gzip.unique",
                log_file=str(logfile),
                rotation="size",
                max_bytes=100,
                backup_count=1,
                compress=True,
            )
            for i in range(10):
                log.info(f"gzip-{i:03d}-" + ("x" * 50))
            log.shutdown()

            files = [f.name for f in tmpdir.glob("*.log*")]
            assert any(f.endswith(".gz") for f in files), f"Expected .gz, got: {files}"
        finally:
            # Restore original module import state for following tests
            if "aqdlog" in sys.modules:
                del sys.modules["aqdlog"]
            importlib.import_module("aqdlog")


class TestGracefulShutdown:
    def test_shutdown_cleans_handlers(self):
        log = logger("test.shutdown.unique", level="ERROR", log_file="/dev/null")
        # QueueHandler and ConsoleHandler should be present
        assert len(log.handlers) > 0
        log.shutdown()
        # QueueHandler and ConsoleHandler gone
        assert len(log.handlers) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
