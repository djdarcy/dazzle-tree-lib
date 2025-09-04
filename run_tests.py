#!/usr/bin/env python
"""
Simple Test Runner for DazzleTreeLib
=====================================

Runs all tests except slow ones and one-offs.
Shows which tests are slow and why.

Usage:
    python run_tests.py           # Run all non-slow tests
    python run_tests.py --slow    # Show info about slow tests
    python run_tests.py --all     # Run everything including slow tests
"""

import subprocess
import sys
import argparse
from pathlib import Path


def run_tests(include_slow=False):
    """Run the test suite."""
    cmd = [
        sys.executable, "-m", "pytest",
        "--ignore=tests/one-offs",  # Always ignore one-offs
        "--tb=short",               # Short traceback format
        "--durations=10",            # Show 10 slowest tests
        "-v"                         # Verbose output
    ]
    
    if not include_slow:
        cmd.extend(["-m", "not slow"])
        print("Running all tests EXCEPT slow tests and one-offs...")
        print("=" * 60)
    else:
        print("Running ALL tests including slow ones (but not one-offs)...")
        print("=" * 60)
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode


def show_slow_tests():
    """Show information about slow tests."""
    print("=" * 60)
    print("SLOW TESTS ANALYSIS")
    print("=" * 60)
    print("\nThe following tests are marked as @pytest.mark.slow:")
    print("-" * 60)
    
    slow_tests = [
        # test_depth_tracking.py tests
        ("test_depth_tracking.py::TestDepthPerformance::test_depth_tracking_overhead",
         "Tests overhead of depth tracking on 10,000 nodes",
         "~5-10s", "Performance baseline measurement"),
        
        ("test_depth_tracking.py::TestDepthPerformance::test_filter_by_depth_performance",
         "Tests filter_by_depth with 10,000 nodes at various depths",
         "~5-10s", "Ensures depth filtering remains efficient"),
        
        # test_depth_tracking_performance_enhanced.py tests
        ("test_depth_tracking_performance_enhanced.py::test_large_tree_performance_with_progress",
         "Tests traversal of 10,000+ nodes with progress tracking",
         "~10-20s", "Validates performance at scale with progress bars"),
        
        ("test_depth_tracking_performance_enhanced.py::test_filter_performance_realistic",
         "Tests realistic filesystem simulation with 1,000 directories",
         "~5-15s", "Simulates real-world directory structures"),
        
        # test_performance_async.py tests
        ("test_performance_async.py::test_traversal_speed_medium_tree",
         "Benchmarks async traversal on medium tree (1,000 nodes)",
         "~5-10s", "Performance benchmark for medium datasets"),
        
        ("test_performance_async.py::test_traversal_speed_large_tree",
         "Benchmarks async traversal on large tree (10,000 nodes)",
         "~30-60s", "Performance benchmark for large datasets"),
        
        # test_performance.py tests (ENTIRE CLASS - 13 tests)
        ("test_performance.py::TestPerformance (13 tests)",
         "Comprehensive sync performance test suite",
         "~60-120s", "Creates 32,768+ directories in setUpClass! Tests caching, strategies, depth, filtering")
    ]
    
    for test_name, description, duration, reason in slow_tests:
        print(f"\n* {test_name}")
        print(f"   Description: {description}")
        print(f"   Duration: {duration}")
        print(f"   Why slow: {reason}")
    
    print("\n" + "=" * 60)
    print("HOW TO RUN SLOW TESTS")
    print("=" * 60)
    
    print("""
1. Run ALL slow tests:
   python -m pytest -m slow -v

2. Run a specific slow test:
   python -m pytest tests/test_depth_tracking.py::TestDepthPerformance::test_depth_tracking_overhead -v

3. Run slow tests with timeout (recommended):
   python -m pytest -m slow --timeout=120 -v

4. Run everything including slow tests:
   python run_tests.py --all
   
Note: These tests are slow because they:
- Process thousands of nodes to measure performance
- Simulate realistic large-scale scenarios
- Provide benchmarking data for optimization
- Ensure the library scales well

They are important for:
- Performance regression detection
- Benchmarking improvements
- Validating scalability claims
- Testing edge cases at scale

But they're excluded from regular test runs because:
- They take 60-120 seconds total
- They don't test functionality (just performance)
- They can timeout in CI environments
""")
    
    print("=" * 60)
    print("RECOMMENDATION")
    print("=" * 60)
    print("""
For commit validation, run:
  python run_tests.py         (excludes slow tests)

For full validation before release, run:
  python run_tests.py --all   (includes slow tests)

The slow tests should be run:
- Before major releases
- After performance optimizations
- When changing core traversal logic
- Weekly in CI pipeline
""")


def main():
    parser = argparse.ArgumentParser(description="Test runner for DazzleTreeLib")
    parser.add_argument("--slow", action="store_true", help="Show info about slow tests")
    parser.add_argument("--all", action="store_true", help="Run all tests including slow ones")
    
    args = parser.parse_args()
    
    if args.slow:
        show_slow_tests()
        return 0
    
    return run_tests(include_slow=args.all)


if __name__ == "__main__":
    sys.exit(main())