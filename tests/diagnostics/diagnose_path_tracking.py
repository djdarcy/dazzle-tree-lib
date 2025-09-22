#!/usr/bin/env python
"""
Track which code path is actually being taken during test execution.
This will definitively show if the fast path is always triggered.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

# Create a modified version of the adapter with tracking
TRACKING_CODE = '''
import time
from pathlib import Path
from typing import Any, AsyncIterator

# Add tracking globals
_fast_path_count = 0
_safe_path_count = 0
_fast_cache_hits = 0
_safe_cache_hits = 0

original_get_children = CompletenessAwareCacheAdapter.get_children

async def tracked_get_children(self, node: Any) -> AsyncIterator[Any]:
    global _fast_path_count, _safe_path_count, _fast_cache_hits, _safe_cache_hits

    # Check which path we're taking
    if not self.enable_oom_protection:
        _fast_path_count += 1
        # Check if we'll get a cache hit
        path = node.path if hasattr(node, 'path') else str(node)
        if not isinstance(path, Path):
            path = Path(path) if isinstance(path, str) else path
        depth = self._depth_context if self._depth_context is not None else 1
        cache_key = self._get_cache_key(path, depth)
        if cache_key in self.cache:
            _fast_cache_hits += 1
    else:
        _safe_path_count += 1
        # Similar check for safe mode
        path = node.path if hasattr(node, 'path') else str(node)
        if not isinstance(path, Path):
            path = Path(path) if isinstance(path, str) else path
        depth = self._depth_context if self._depth_context is not None else 1
        cache_key = self._get_cache_key(path, depth)
        if cache_key in self.cache:
            _safe_cache_hits += 1

    # Call original method
    async for child in original_get_children(self, node):
        yield child

# Monkey patch the method
CompletenessAwareCacheAdapter.get_children = tracked_get_children

# Add reporting at the end
import atexit

def report_paths():
    print(f"\\n=== PATH TRACKING REPORT ===")
    print(f"Fast path calls: {_fast_path_count}")
    print(f"Safe path calls: {_safe_path_count}")
    print(f"Fast cache hits: {_fast_cache_hits}")
    print(f"Safe cache hits: {_safe_cache_hits}")
    if _fast_path_count > 0:
        print(f"Fast cache hit rate: {_fast_cache_hits / _fast_path_count * 100:.1f}%")
    if _safe_path_count > 0:
        print(f"Safe cache hit rate: {_safe_cache_hits / _safe_path_count * 100:.1f}%")

atexit.register(report_paths)
'''

def create_tracked_test():
    """Create a test file with tracking injected."""

    # Read the original adapter
    adapter_file = Path("dazzletreelib/aio/adapters/cache_completeness_adapter.py")
    original_content = adapter_file.read_text()

    # Create a temporary file with tracking
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        # Write original content
        f.write(original_content)
        f.write("\n\n# === TRACKING CODE INJECTED ===\n")
        f.write(TRACKING_CODE)
        temp_file = f.name

    return temp_file

def run_test_with_tracking():
    """Run the test with path tracking enabled."""

    print("=" * 80)
    print("PATH TRACKING DIAGNOSTIC")
    print("=" * 80)

    # Create a test script that imports our tracked version
    test_script = '''
import sys
import asyncio
from pathlib import Path

# Import with tracking
exec(open('track_adapter.py').read())

async def run_test():
    """Run the performance test."""
    from tests.test_issue_29_performance_realistic import MockNode, MockAdapter

    operations = 1000
    paths = [Path(f"/test/path_{i}") for i in range(operations)]

    # Test SAFE mode
    mock_adapter_safe = MockAdapter(children_per_node=10)
    safe_adapter = CompletenessAwareCacheAdapter(
        mock_adapter_safe,
        enable_oom_protection=True,
        max_entries=10000
    )

    import time
    start = time.perf_counter()
    for path in paths:
        node = MockNode(path)
        children = []
        async for child in safe_adapter.get_children(node):
            children.append(child)
    safe_time = time.perf_counter() - start

    # Test FAST mode
    mock_adapter_fast = MockAdapter(children_per_node=10)
    fast_adapter = CompletenessAwareCacheAdapter(
        mock_adapter_fast,
        enable_oom_protection=False
    )

    start = time.perf_counter()
    for path in paths:
        node = MockNode(path)
        children = []
        async for child in fast_adapter.get_children(node):
            children.append(child)
    fast_time = time.perf_counter() - start

    print(f"Safe time: {safe_time:.3f}s")
    print(f"Fast time: {fast_time:.3f}s")
    print(f"Improvement: {(safe_time - fast_time) / safe_time * 100:.1f}%")

    if fast_time > safe_time:
        print("WARNING: Fast mode was SLOWER!")
        return False
    return True

# Run multiple times to catch intermittent issues
success_count = 0
for i in range(10):
    print(f"\\nIteration {i+1}/10:")
    result = asyncio.run(run_test())
    if result:
        success_count += 1

print(f"\\nFinal: {success_count}/10 passed")
'''

    # Write the test script
    with open("test_with_tracking.py", "w") as f:
        f.write(test_script)

    # Copy adapter with tracking
    tracked_file = create_tracked_test()
    import shutil
    shutil.copy(tracked_file, "track_adapter.py")

    # Run the test
    try:
        proc = subprocess.run(
            [sys.executable, "test_with_tracking.py"],
            capture_output=True,
            text=True,
            timeout=60
        )
        print(proc.stdout)
        if proc.stderr:
            print("Errors:", proc.stderr)
    finally:
        # Cleanup
        Path("test_with_tracking.py").unlink(missing_ok=True)
        Path("track_adapter.py").unlink(missing_ok=True)
        Path(tracked_file).unlink(missing_ok=True)

if __name__ == "__main__":
    # Simpler approach - just run the existing test multiple times and watch for failures
    print("Running simplified path tracking test...")
    print("This will run the actual pytest test 10 times and look for failures.\n")

    failures = []
    for i in range(10):
        print(f"Run {i+1}/10: ", end="", flush=True)

        proc = subprocess.run(
            [sys.executable, "-m", "pytest",
             "tests/test_issue_29_performance_realistic.py::TestRealisticPerformance::test_safe_vs_fast_mode_comparison",
             "-xvs", "--tb=no"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if proc.returncode == 0:
            # Extract performance
            for line in proc.stdout.split('\n'):
                if "Performance improvement:" in line:
                    pct = line.split(":")[1].strip()
                    print(f"PASSED ({pct})")
                    break
            else:
                print("PASSED")
        else:
            # Extract failure reason
            for line in proc.stdout.split('\n'):
                if "Performance improvement:" in line:
                    pct = line.split(":")[1].strip()
                    print(f"FAILED (Fast mode was slower: {pct})")
                    failures.append(i+1)
                    break
            else:
                print("FAILED (unknown reason)")
                failures.append(i+1)

    print(f"\n{'='*80}")
    print(f"SUMMARY: {10 - len(failures)}/10 passed")
    if failures:
        print(f"Failed on iterations: {failures}")
        print("\nThe intermittent failure is confirmed!")
        print("This suggests the issue is real and not just a measurement artifact.")
    else:
        print("All tests passed - the issue may be resolved or very rare.")