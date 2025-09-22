"""Test to understand timing stability issues."""

import asyncio
import time
from pathlib import Path
import statistics
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dazzletreelib.aio.adapters.cache_completeness_adapter import CompletenessAwareCacheAdapter


class MockNode:
    def __init__(self, path):
        self.path = Path(path) if not isinstance(path, Path) else path


class MockAdapter:
    def __init__(self, children_per_node=10):
        self.children_per_node = children_per_node
        self.call_count = 0
    
    async def get_children(self, node):
        self.call_count += 1
        for i in range(self.children_per_node):
            yield MockNode(node.path / f"child_{i}")


async def test_timing_stability():
    """Test timing stability with warmup and statistics."""
    
    print("=== TIMING STABILITY TEST ===\n")
    
    # Configuration
    num_paths = 1000  # More paths for stable timing
    num_warmup = 3    # Warmup rounds
    num_test = 10     # Test rounds
    
    paths = [Path(f"/test/path_{i}") for i in range(num_paths)]
    
    async def run_test(enable_protection):
        """Run a single test iteration."""
        mock = MockAdapter(children_per_node=10)
        adapter = CompletenessAwareCacheAdapter(
            mock,
            enable_oom_protection=enable_protection,
            max_entries=10000 if enable_protection else 0,
            max_cache_depth=50 if enable_protection else 0,
            max_path_depth=30 if enable_protection else 0,
            max_tracked_nodes=10000 if enable_protection else 0
        )
        
        start = time.perf_counter()
        for path in paths:
            node = MockNode(path)
            async for _ in adapter.get_children(node):
                pass
        return time.perf_counter() - start
    
    # Warmup
    print("Warming up...")
    for _ in range(num_warmup):
        await run_test(True)
        await run_test(False)
    
    # Actual testing
    print(f"Running {num_test} test rounds with {num_paths} paths each...\n")
    
    safe_times = []
    fast_times = []
    
    for round_num in range(num_test):
        # Alternate order to avoid systematic bias
        if round_num % 2 == 0:
            safe_time = await run_test(True)
            fast_time = await run_test(False)
        else:
            fast_time = await run_test(False)
            safe_time = await run_test(True)
        
        safe_times.append(safe_time)
        fast_times.append(fast_time)
        
        improvement = (safe_time - fast_time) / safe_time * 100
        status = "PASS" if fast_time < safe_time else "FAIL"
        print(f"Round {round_num + 1:2}: Safe={safe_time:.4f}s, Fast={fast_time:.4f}s, "
              f"Improvement={improvement:6.1f}% {status}")
    
    # Statistics
    print("\n=== STATISTICS ===")
    
    safe_mean = statistics.mean(safe_times)
    safe_stdev = statistics.stdev(safe_times)
    safe_cv = (safe_stdev / safe_mean) * 100  # Coefficient of variation
    
    fast_mean = statistics.mean(fast_times)
    fast_stdev = statistics.stdev(fast_times)
    fast_cv = (fast_stdev / fast_mean) * 100
    
    improvements = [(s - f) / s * 100 for s, f in zip(safe_times, fast_times)]
    improvement_mean = statistics.mean(improvements)
    improvement_stdev = statistics.stdev(improvements)
    
    print(f"\nSafe Mode:")
    print(f"  Mean: {safe_mean:.4f}s ± {safe_stdev:.4f}s")
    print(f"  CV: {safe_cv:.1f}% (lower is more stable)")
    print(f"  Range: {min(safe_times):.4f}s - {max(safe_times):.4f}s")
    
    print(f"\nFast Mode:")
    print(f"  Mean: {fast_mean:.4f}s ± {fast_stdev:.4f}s")
    print(f"  CV: {fast_cv:.1f}% (lower is more stable)")
    print(f"  Range: {min(fast_times):.4f}s - {max(fast_times):.4f}s")
    
    print(f"\nImprovement:")
    print(f"  Mean: {improvement_mean:.1f}% ± {improvement_stdev:.1f}%")
    print(f"  Range: {min(improvements):.1f}% - {max(improvements):.1f}%")
    
    # Success rate
    successes = sum(1 for f, s in zip(fast_times, safe_times) if f < s)
    print(f"  Success rate: {successes}/{num_test} ({successes/num_test*100:.0f}%)")
    
    # Recommendation
    print("\n=== ANALYSIS ===")
    
    if improvement_mean < 0:
        print("PROBLEM: Fast mode is slower on average!")
        print("   This indicates a logic error, not just timing variance.")
    elif improvement_mean < 10:
        print("WARNING: Improvement is marginal (<10%).")
        print("   The overhead reduction might not justify the complexity.")
    elif improvement_stdev > improvement_mean / 2:
        print("WARNING: High variance in improvements.")
        print("   Results are unstable, possibly due to:")
        print("   - Background processes")
        print("   - Python GC interference")
        print("   - CPU frequency scaling")
    else:
        print("GOOD: Fast mode shows consistent improvement.")
    
    if safe_cv > 10 or fast_cv > 10:
        print(f"\nHigh timing variance detected (CV > 10%).")
        print("   Consider:")
        print("   - Running with higher priority")
        print("   - Disabling CPU frequency scaling")
        print("   - Using more iterations")


if __name__ == "__main__":
    asyncio.run(test_timing_stability())