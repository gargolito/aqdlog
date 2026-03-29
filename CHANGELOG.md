# Changelog

All notable changes to `aqdlog` will be documented in this file.

## 2.1.0 - 2026-03-29

### Added
- Added `silent=True` to `aqdlog.logger(...)` for file-only logging.
- Silent mode disables the built-in console fallback and sets `propagate = False` so records do not bubble into parent/root handlers such as journald or syslog integrations.

### Documentation
- Added README guidance and an example script entry showing file-only, non-propagating logger configuration.
- Added test coverage for silent mode with and without `log_file`.
