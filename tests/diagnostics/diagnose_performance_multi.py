#!/usr/bin/env python
"""
Multi-iteration diagnostic script to catch intermittent performance failures.
Runs tests multiple times to identify patterns.
"""

import subprocess
import sys
import json
import time
from pathlib import Path
from datetime import datetime

def run_performance_tests(iteration):
    """Run the performance tests and return results"""
    cmd = [
        sys.executable, '-m', 'pytest',
        'tests/test_issue_29_performance_realistic.py::TestRealisticPerformance::test_safe_vs_fast_mode_comparison',
        'tests/test_issue_21_cache_memory_limits.py::TestPerformance::test_performance_regression_under_5_percent',
        '-xvs', '--tb=short'
    ]

    result = {
        'iteration': iteration,
        'timestamp': datetime.now().isoformat(),
        'passed': False,
        'metrics': {}
    }

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        output = proc.stdout + proc.stderr
        result['passed'] = proc.returncode == 0

        # Extract metrics
        for line in output.split('\n'):
            if 'Safe mode (protection ON):' in line:
                try:
                    time_str = line.split(':')[1].strip().replace('s', '')
                    result['metrics']['safe_time'] = float(time_str)
                except:
                    pass
            elif 'Fast mode (protection OFF):' in line:
                try:
                    time_str = line.split(':')[1].strip().replace('s', '')
                    result['metrics']['fast_time'] = float(time_str)
                except:
                    pass
            elif 'Performance improvement:' in line:
                try:
                    pct = line.split(':')[1].strip().replace('%', '')
                    result['metrics']['improvement'] = float(pct)
                except:
                    pass
            elif 'Performance regression' in line and 'exceeds' in line:
                result['metrics']['regression_exceeded'] = True

    except Exception as e:
        result['error'] = str(e)

    return result

def main():
    """Run multiple iterations and analyze results"""
    print("=" * 80)
    print("MULTI-ITERATION PERFORMANCE DIAGNOSTIC")
    print("=" * 80)
    print(f"Starting at: {datetime.now()}")
    print("\nRunning 10 iterations to catch intermittent failures...")

    results = []
    for i in range(1, 11):
        print(f"\nIteration {i}/10...", end=' ')
        result = run_performance_tests(i)
        results.append(result)

        if result['passed']:
            print(f"PASSED", end='')
            if 'improvement' in result['metrics']:
                print(f" (improvement: {result['metrics']['improvement']:.1f}%)")
            else:
                print()
        else:
            print(f"FAILED")
            if 'improvement' in result['metrics']:
                print(f"  Fast mode was {-result['metrics']['improvement']:.1f}% SLOWER")

        # Brief pause between iterations
        time.sleep(2)

    # Analyze results
    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)

    passed = sum(1 for r in results if r['passed'])
    failed = 10 - passed

    print(f"\nResults: {passed} passed, {failed} failed")

    if failed > 0:
        print("\nFailure pattern:")
        for r in results:
            if not r['passed']:
                print(f"  Iteration {r['iteration']}: ", end='')
                if 'improvement' in r['metrics']:
                    print(f"Fast mode {-r['metrics']['improvement']:.1f}% slower")
                else:
                    print("Unknown failure")

    # Calculate statistics
    improvements = [r['metrics']['improvement'] for r in results
                   if 'improvement' in r['metrics']]

    if improvements:
        avg_improvement = sum(improvements) / len(improvements)
        min_improvement = min(improvements)
        max_improvement = max(improvements)

        print(f"\nPerformance statistics:")
        print(f"  Average improvement: {avg_improvement:.1f}%")
        print(f"  Best improvement: {max_improvement:.1f}%")
        print(f"  Worst improvement: {min_improvement:.1f}%")
        print(f"  Variance: {max_improvement - min_improvement:.1f}%")

    # Save detailed results
    report_file = f"multi_diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to: {report_file}")

    # Recommendations
    if failed > 0:
        if failed > 5:
            print("\nDIAGNOSIS: Consistent failure - likely a code bug")
        elif failed > 2:
            print("\nDIAGNOSIS: Intermittent failure - likely timing or resource issue")
        else:
            print("\nDIAGNOSIS: Rare failure - likely system load or CPU throttling")
    else:
        print("\nDIAGNOSIS: All tests passed - issue may be resolved or very rare")

if __name__ == "__main__":
    main()