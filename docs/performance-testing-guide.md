# Performance Testing Guide

## Problem Statement

Performance tests can be affected by test execution order due to memory fragmentation, garbage collection state, and cache pollution from previous tests. The `test_fast_mode_performance_advantage` test in particular is sensitive to running after tests that create large numbers of nodes (125k+).

## Solution: Test Isolation

Tests that are sensitive to execution order are marked with `@pytest.mark.interaction_sensitive` and can be run in isolation. Performance benchmarks are marked with `@pytest.mark.benchmark`.

## Test Markers

- **`@pytest.mark.benchmark`**: Performance measurement tests that produce timing results
- **`@pytest.mark.interaction_sensitive`**: Tests whose results are affected by prior test execution (should be run in isolation)
- **`@pytest.mark.slow`**: Tests that take >5 seconds to run
- **`@pytest.mark.stress`**: Tests that create heavy system load
- **`@pytest.mark.flaky`**: Tests sensitive to system load or timing

## Running Tests

### Standard Test Run (Recommended for Development)
```bash
# Run all functional tests, excluding interaction-sensitive tests
python run_tests.py
```

### Interaction-Sensitive Tests (Isolated)
```bash
# Run interaction-sensitive tests in complete isolation
python run_tests.py --isolated

# Or using pytest directly
pytest -m interaction_sensitive -xvs
```

### Benchmark Tests
```bash
# Run all benchmark tests (some may be interaction-sensitive)
python run_tests.py --benchmarks

# Or using pytest directly
pytest -m benchmark -v
```

### All Tests Including Everything
```bash
# Run everything (interaction-sensitive tests may show degradation)
python run_tests.py --all

# Or include sensitive tests in normal run
python run_tests.py --with-sensitive
```

## Test Categories

- **Functional Tests**: Core functionality, should always pass
- **Benchmark Tests**: Performance measurements and speed comparisons
- **Interaction-Sensitive Tests**: Tests affected by prior test execution
- **Slow Tests**: Tests in `tests/performance/` directory that take >5s

## Performance Test Best Practices

1. **Mark appropriately**:
   - Use `@pytest.mark.benchmark` for performance measurements
   - Add `@pytest.mark.interaction_sensitive` if affected by test order
2. **Add GC cleanup**: Start performance tests with `gc.collect()`
3. **Run in isolation**: Use `--isolated` flag for accurate results
4. **Document thresholds**: Clearly state expected performance ratios
5. **Consider cooldown**: Add time.sleep() between tests if needed

## Known Issues

### Test Interaction Effects
- `test_fast_mode_unlimited_tracking` creates ~125,000 nodes
- This affects subsequent performance tests due to:
  - Memory fragmentation
  - GC pressure in wrong generation
  - CPU cache pollution
  - Python object allocation overhead

### Mitigation Strategies
1. **Isolation**: Run performance tests separately
2. **GC Cleanup**: Force garbage collection before tests
3. **Test Markers**: Use pytest markers to control execution
4. **CI/CD**: Run performance tests in separate job/container

## CI/CD Integration

```yaml
# Example GitHub Actions workflow
jobs:
  functional-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: python run_tests.py

  performance-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: python run_tests.py --performance
```

## Validation Results

When run in isolation:
- ✅ Fast mode: ~1.8s
- ✅ Safe mode: ~3.5s
- ✅ Fast mode is 2x faster (as expected)

When run after large tests:
- ❌ Fast mode: ~4.0s
- ❌ Safe mode: ~1.8s
- ❌ Fast mode appears slower (test interaction effect)

## Future Improvements

1. **Process Isolation**: Run each performance test in subprocess
2. **Statistical Analysis**: Multiple runs with statistical validation
3. **Baseline Recording**: Store expected performance ranges
4. **Automated Detection**: Flag when performance degrades

## Cooldown Test Results

Our investigation with `test_performance_with_cooldown.py` shows:
- **Standalone execution**: Fast mode consistently ~1.1x faster (correct)
- **After 125k node test**: Performance remains stable with gc.collect()
- **Cooldown periods**: 0s, 2s, or 5s cooldowns show minimal difference
- **Key finding**: The issue is pytest-specific, not Python runtime

This suggests pytest's test collection or fixture teardown may be the culprit,
not memory fragmentation as initially suspected.

## Commands Reference

```bash
# Quick validation
pytest tests/test_tracking_mode_switching.py::TestModeSwitching::test_fast_mode_performance_advantage -xvs

# Check all benchmark tests
pytest -m benchmark --collect-only

# Check interaction-sensitive tests
pytest -m interaction_sensitive --collect-only

# Run with timeout
pytest -m benchmark --timeout=60

# Profile a specific test
python -m cProfile -s cumtime -m pytest tests/test_tracking_mode_switching.py::TestModeSwitching::test_fast_mode_performance_advantage

# Run cooldown investigation
python tests/one-offs/test_performance_with_cooldown.py
```