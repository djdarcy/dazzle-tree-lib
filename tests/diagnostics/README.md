# Performance Diagnostic Tools

This directory contains diagnostic scripts created during the investigation and resolution of Issue #29 - Performance regression where fast mode was slower than safe mode.

## Background

These scripts were developed to diagnose an intermittent performance issue where the cache adapter's "fast mode" (with OOM protection disabled) was paradoxically 60-87% slower than "safe mode" (with full protection enabled). The issue occurred approximately 20% of the time and was caused by small overheads in the fast path that became significant for cache hits.

## Scripts

### Core Diagnostic Tools

#### `diagnose_performance.py`
Single test diagnostic tool that runs the problematic test in isolation to check if performance issues persist outside the test suite.

#### `diagnose_performance_multi.py`
Multi-iteration statistical analysis tool that runs the test 10 times and reports success rate, identifying intermittent failures.

#### `diagnose_cache_hit_performance.py`
Specifically tests cache hit performance, which was the most sensitive metric and where the final bug (isinstance check) was found.

### Investigation Tools

#### `diagnose_state_contamination.py`
Tests for state leakage between test runs by verifying adapter isolation and checking for module-level caching issues.

#### `diagnose_measurement_swap.py`
Verifies that measurements aren't being swapped between safe and fast modes, includes tests of dict vs OrderedDict performance.

#### `diagnose_path_tracking.py`
Verifies that the fast path is actually being taken by adding tracking to code execution paths.

## JSON Reports

The `*.json` files are diagnostic reports generated during test runs, containing detailed performance metrics and failure patterns.

## Usage

Run any diagnostic script from the project root:

```bash
# Single test diagnostic
python tests/diagnostics/diagnose_performance.py

# Multi-iteration analysis
python tests/diagnostics/diagnose_performance_multi.py

# Cache hit specific test
python tests/diagnostics/diagnose_cache_hit_performance.py
```

## Resolution

The performance issue was ultimately caused by:
1. Lambda function overhead (even no-op lambdas)
2. Debug print statements in tight loops
3. An isinstance() check in the fast path cache hits

Removing these overheads resulted in fast mode being 85-90% faster than safe mode, as originally intended.

## Reference

See the full postmortem at:
`private/claude/2025-09-13__11-01-18__full-postmortem_performance-regression-fast-mode-slower.md`