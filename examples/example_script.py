#!/usr/bin/env python
# -*- coding: utf-8  -*-
"""
Example usage of aqdlog:
- Size rotation → compresses with zstd/gzip
- Time rotation → daily logs kept 2 days
- Demonstrates graceful shutdown & duplicate suppression
"""

import os
import time
import tempfile
from pathlib import Path
from aqdlog import logger

def example_size():
    print("📝 EXAMPLE: Size rotation (max 500B, keep 2 rotated files, compress=True)")
    tmpdir = Path(tempfile.gettempdir()) / "aqdlog_example_size"
    tmpdir.mkdir(exist_ok=True)
    logfile = tmpdir / "app.log"

    log = logger(
        "example.size",
        log_file=str(logfile),
        rotation="size",
        max_bytes=500,
        backup_count=2,
        compress=True,
    )

    # Log enough to cause rotation
    for i in range(25):
        log.info(f"Log entry #{i:03d} — " + "x" * 60)
    log.shutdown()

    print("   Files created:")
    for f in sorted(tmpdir.glob("*.log*")):
        print(f"   - {f.name} ({f.stat().st_size} bytes)")

def example_time():
    print("\n📝 EXAMPLE: Time rotation (midnight, keep 2 days, compress=True)")
    tmpdir = Path(tempfile.gettempdir()) / "aqdlog_example_time"
    tmpdir.mkdir(exist_ok=True)
    logfile = tmpdir / "timed.log"

    log = logger(
        "example.time",
        log_file=str(logfile),
        rotation="time",
        when="midnight",
        backup_count=2,
        compress=True,
    )

    log.info("Created today's log at %s", time.strftime("%Y-%m-%d %H:%M:%S"))
    log.shutdown()

    print("   Files created (all timestamps from midnight rollover logic):")
    for f in sorted(tmpdir.glob("*.log*")):
        print(f"   - {f.name}")

def example_no_compress():
    print("\n📝 EXAMPLE: Size rotation WITHOUT compression (backup_count=2, compress=False)")
    tmpdir = Path(tempfile.gettempdir()) / "aqdlog_no_compress"
    tmpdir.mkdir(exist_ok=True)
    logfile = tmpdir / "no_compression.log"

    log = logger(
        "example.no_compress",
        log_file=str(logfile),
        rotation="size",
        max_bytes=1_500,
        backup_count=2,
        compress=False,
    )

    for i in range(5):
        log.info(f"Uncompressed log #{i}: " + "y" * 50)

    log.shutdown()
    print("   No .zst files! Only .log, .log.1, .log.2, etc.")
    for f in sorted(tmpdir.glob("*.log*")):
        print(f"   - {f.name} ({f.stat().st_size} bytes)")

def example_backup_zero():
    print("\n📝 EXAMPLE: backup_count=0 → NO rotation, even if max_bytes exceeded")
    tmpdir = Path(tempfile.gettempdir()) / "aqdlog_backup_zero"
    tmpdir.mkdir(exist_ok=True)
    logfile = tmpdir / "no_rotation.log"

    log = logger(
        "example.no_rotation",
        log_file=str(logfile),
        rotation="size",
        max_bytes=500,
        backup_count=0,  # ← disabled
        compress=True,
    )

    for i in range(10):
        log.info(f"No-rotation entry #{i}: " + "z" * 100)

    log.shutdown()
    print("   Only one file (no .1.zst):")
    for f in sorted(tmpdir.glob("*")):
        print(f"   - {f.name} ({f.stat().st_size} bytes)")

def example_duplicate_filter():
    print("\n📝 EXAMPLE: Duplicate message filter (keeps last 10 unique messages)")
    import random

    log = logger("example.dups", level="INFO", log_file="/dev/null", backup_count=0)

    for _ in range(5):
        log.info("This exact message appears twice")
    # Should suppress duplicates (only one "This exact message...")
    log.info("A new message!")
    log.info("Another unique message.")
    # Now trigger new messages and clear old
    for i in range(8):
        log.info(f"Message {i}: " + "a" * 20)

    log.shutdown()

if __name__ == "__main__":
    # All examples (will run on real temp files)
    example_size()
    example_time()
    example_no_compress()
    example_backup_zero()
    example_duplicate_filter()

    print("\n✅ All examples completed. Check temp files in your OS temp directory (e.g., /tmp).")
