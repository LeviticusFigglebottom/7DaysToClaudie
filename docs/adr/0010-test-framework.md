# ADR-0010: GUT 9.7.1, vendored via jsDelivr

**Status**: Accepted (2026-10-04)

## Context
The brief allows gdUnit4 or GUT. GitHub release archives were unreachable from the build
container, but jsDelivr mirrors tagged repository files.

## Decision
Vendor **GUT 9.7.1** (MIT) into `game/addons/gut` with `tools/setup/vendor_gut.py` (file list from
data.jsdelivr.com, files from cdn.jsdelivr.net, pinned version in `tools/versions.env`). Tests live
in `game/tests/unit` and `game/tests/integration`; `make test` runs them headless and writes JUnit
XML to `build/test-results/`. GUT fails a test on unexpected `push_error`; tests declare expected
errors with `assert_push_error_count`.

## Consequences
GUT's CLI and doubles work headless; it is simpler to vendor than gdUnit4 (no editor-version
coupling).
