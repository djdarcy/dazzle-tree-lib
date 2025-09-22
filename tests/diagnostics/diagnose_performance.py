#!/usr/bin/env python
"""
Diagnostic script for performance test failures in DazzleTreeLib.
Runs tests in controlled environment and reports findings.

Usage: python diagnose_performance.py
"""

import subprocess
import time
import json
import sys
import os
from pathlib import Path
from datetime import datetime

class PerformanceDiagnostic:
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'tests': [],
            'summary': {}
        }
        self.failing_tests = [
            'tests/test_issue_29_performance_realistic.py::TestRealisticPerformance::test_safe_vs_fast_mode_comparison',
            'tests/test_issue_21_cache_memory_limits.py::TestPerformance::test_performance_regression_under_5_percent',
        ]

    def run_test_isolated(self, test_path, test_num, total_tests):
        """Run single test in fresh Python process"""
        print(f"\n[{test_num}/{total_tests}] Running isolated test: {test_path}")
        print("=" * 80)

        result = {
            'test': test_path,
            'mode': 'isolated',
            'passed': False,
            'output': '',
            'performance_metrics': {}
        }

        try:
            # Run test capturing output
            cmd = [sys.executable, '-m', 'pytest', test_path, '-xvs', '--tb=short']
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            result['output'] = proc.stdout + proc.stderr
            result['passed'] = proc.returncode == 0

            # Extract performance metrics from output
            if 'Safe mode' in result['output']:
                lines = result['output'].split('\n')
                for line in lines:
                    if 'Safe mode' in line and 's' in line:
                        try:
                            time_str = line.split(':')[1].strip().replace('s', '')
                            result['performance_metrics']['safe_mode_time'] = float(time_str)
                        except:
                            pass
                    elif 'Fast mode' in line and 's' in line:
                        try:
                            time_str = line.split(':')[1].strip().replace('s', '')
                            result['performance_metrics']['fast_mode_time'] = float(time_str)
                        except:
                            pass
                    elif 'Performance improvement' in line:
                        try:
                            pct = line.split(':')[1].strip().replace('%', '')
                            result['performance_metrics']['improvement_pct'] = float(pct)
                        except:
                            pass
                    elif 'Performance regression' in line and '%' in line:
                        # Extract regression percentage
                        import re
                        match = re.search(r'(\d+\.?\d*)%', line)
                        if match:
                            result['performance_metrics']['regression_pct'] = float(match.group(1))

            # Print summary
            status = "PASSED" if result['passed'] else "FAILED"
            print(f"Status: {status}")
            if result['performance_metrics']:
                print(f"Metrics: {json.dumps(result['performance_metrics'], indent=2)}")

        except subprocess.TimeoutExpired:
            result['output'] = "Test timed out after 60 seconds"
            print("Status: TIMEOUT")
        except Exception as e:
            result['output'] = f"Error running test: {str(e)}"
            print(f"Status: ERROR - {str(e)}")

        self.results['tests'].append(result)
        return result

    def run_tests_together(self):
        """Run tests together as they would in suite"""
        print(f"\n[SUITE] Running tests together in suite mode")
        print("=" * 80)

        result = {
            'test': 'all_together',
            'mode': 'suite',
            'passed': False,
            'output': '',
            'performance_metrics': {}
        }

        try:
            # Run both tests together
            cmd = [sys.executable, '-m', 'pytest'] + self.failing_tests + ['-xvs', '--tb=short']
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            result['output'] = proc.stdout + proc.stderr
            result['passed'] = proc.returncode == 0

            # Parse output for metrics
            self._parse_metrics(result)

            # Print summary
            status = "PASSED" if result['passed'] else "FAILED"
            print(f"Status: {status}")
            if result['performance_metrics']:
                print(f"Metrics: {json.dumps(result['performance_metrics'], indent=2)}")

        except Exception as e:
            result['output'] = f"Error: {str(e)}"
            print(f"Status: ERROR - {str(e)}")

        self.results['tests'].append(result)
        return result

    def check_fast_path_usage(self):
        """Add temporary debug code to verify fast path usage"""
        print(f"\n[DEBUG] Checking fast path usage")
        print("=" * 80)

        # Read the adapter file
        adapter_file = Path("dazzletreelib/aio/adapters/cache_completeness_adapter.py")
        content = adapter_file.read_text()

        # Check if fast path code exists
        has_fast_path = "# Fast mode optimization: minimal overhead path" in content
        has_condition = "if not self.enable_oom_protection:" in content

        print(f"Fast path code present: {'YES' if has_fast_path else 'NO'}")
        print(f"Fast path condition present: {'YES' if has_condition else 'NO'}")

        # Check for debug output (should be removed in production)
        has_debug = "DEBUG: FAST PATH TRIGGERED" in content or "DEBUG: SAFE PATH TRIGGERED" in content
        if has_debug:
            print("WARNING: Debug output found in code - this may affect performance!")

        return has_fast_path and has_condition

    def _parse_metrics(self, result):
        """Parse performance metrics from test output"""
        if 'Safe mode' in result['output']:
            lines = result['output'].split('\n')
            for line in lines:
                if 'Safe mode' in line and 's' in line:
                    try:
                        time_str = line.split(':')[1].strip().replace('s', '')
                        result['performance_metrics']['safe_mode_time'] = float(time_str)
                    except:
                        pass
                elif 'Fast mode' in line and 's' in line:
                    try:
                        time_str = line.split(':')[1].strip().replace('s', '')
                        result['performance_metrics']['fast_mode_time'] = float(time_str)
                    except:
                        pass
                elif 'Performance improvement' in line:
                    try:
                        pct = line.split(':')[1].strip().replace('%', '')
                        result['performance_metrics']['improvement_pct'] = float(pct)
                    except:
                        pass

    def run_with_verification(self):
        """Run test with inline verification of fast path"""
        print(f"\n[VERIFY] Running with fast path verification")
        print("=" * 80)

        # Create a temporary test that verifies fast path
        verification_test = '''
import sys
import asyncio
from pathlib import Path
sys.path.insert(0, ".")

async def verify_fast_path():
    from dazzletreelib.aio.adapters.cache_completeness_adapter import CompletenessAwareCacheAdapter

    # Create mock adapter
    class MockAdapter:
        async def get_children(self, node):
            for i in range(10):
                yield f"child_{i}"

    # Test fast mode
    fast_adapter = CompletenessAwareCacheAdapter(
        MockAdapter(),
        enable_oom_protection=False
    )

    # Check the flag
    print(f"Fast mode enabled: {not fast_adapter.enable_oom_protection}")
    print(f"Using OrderedDict: {type(fast_adapter.cache).__name__}")
    print(f"Should update LRU: {fast_adapter.should_update_lru}")

    # Try to get children
    children = []
    async for child in fast_adapter.get_children(Path("/test")):
        children.append(child)

    print(f"Got {len(children)} children")
    return not fast_adapter.enable_oom_protection

if __name__ == "__main__":
    result = asyncio.run(verify_fast_path())
    sys.exit(0 if result else 1)
'''

        # Write and run verification
        verify_file = Path("temp_verify_fast_path.py")
        verify_file.write_text(verification_test)

        try:
            proc = subprocess.run(
                [sys.executable, str(verify_file)],
                capture_output=True,
                text=True,
                timeout=10
            )
            print("Verification output:")
            print(proc.stdout)
            if proc.stderr:
                print("Errors:", proc.stderr)

            return proc.returncode == 0
        finally:
            verify_file.unlink(missing_ok=True)

    def generate_report(self):
        """Generate comprehensive diagnostic report"""
        print("\n" + "=" * 80)
        print("DIAGNOSTIC REPORT SUMMARY")
        print("=" * 80)

        # Analyze results
        isolated_pass = sum(1 for t in self.results['tests']
                          if t['mode'] == 'isolated' and t['passed'])
        isolated_total = sum(1 for t in self.results['tests']
                           if t['mode'] == 'isolated')

        suite_pass = sum(1 for t in self.results['tests']
                        if t['mode'] == 'suite' and t['passed'])

        print(f"\nTest Results:")
        print(f"  Isolated: {isolated_pass}/{isolated_total} passed")
        print(f"  Suite: {'PASSED' if suite_pass else 'FAILED'}")

        # Check for pattern
        if isolated_pass == isolated_total and not suite_pass:
            print("\nISSUE CONFIRMED: Tests pass individually but fail in suite!")
            print("This indicates test contamination or state issues.")
            self.results['summary']['issue'] = 'test_contamination'
        elif isolated_pass == 0:
            print("\nISSUE: Tests fail even in isolation!")
            print("This indicates a fundamental code problem.")
            self.results['summary']['issue'] = 'code_bug'
        else:
            print("\nTests behave consistently")
            self.results['summary']['issue'] = 'none'

        # Performance analysis
        print(f"\nPerformance Metrics:")
        for test in self.results['tests']:
            if test.get('performance_metrics'):
                print(f"\n  {test['test'][:50]}... ({test['mode']}):")
                metrics = test['performance_metrics']
                if 'safe_mode_time' in metrics:
                    print(f"    Safe mode: {metrics.get('safe_mode_time', 'N/A')}s")
                if 'fast_mode_time' in metrics:
                    print(f"    Fast mode: {metrics.get('fast_mode_time', 'N/A')}s")
                if 'improvement_pct' in metrics:
                    print(f"    Improvement: {metrics.get('improvement_pct', 'N/A')}%")
                if 'regression_pct' in metrics:
                    print(f"    Regression: {metrics.get('regression_pct', 'N/A')}%")

        # Save full report
        report_file = Path(f"diagnostic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\nFull report saved to: {report_file}")

        return self.results['summary'].get('issue', 'unknown')

    def run_all_diagnostics(self):
        """Run complete diagnostic suite"""
        print("=" * 80)
        print("PERFORMANCE DIAGNOSTIC TOOL")
        print("=" * 80)
        print(f"Starting at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Check fast path exists
        if not self.check_fast_path_usage():
            print("\nFast path code not found! Please check implementation.")
            return

        # Verify fast path works
        if not self.run_with_verification():
            print("\nFast path verification failed!")

        # Run tests individually
        for i, test in enumerate(self.failing_tests, 1):
            self.run_test_isolated(test, i, len(self.failing_tests))
            time.sleep(1)  # Brief pause between tests

        # Run tests together
        self.run_tests_together()

        # Generate report
        issue = self.generate_report()

        # Provide recommendations
        print("\n" + "=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)

        if issue == 'test_contamination':
            print("""
The issue is test contamination. Recommended actions:
1. Run with pytest-forked to isolate tests: pip install pytest-forked && pytest --forked
2. Check for class/module variable modifications
3. Look for tests that don't properly clean up
4. Consider adding setUp/tearDown to reset state
5. Use the binary search method to find the contaminating test
""")
        elif issue == 'code_bug':
            print("""
The issue is in the code itself. Recommended actions:
1. Add debug output to verify fast path is taken
2. Check that enable_oom_protection is actually False
3. Verify the fast path logic is correct
4. Profile the code to find the slow section
5. Check for any exceptions being silently caught
""")
        else:
            print("No clear issue pattern detected. Manual investigation needed.")

if __name__ == "__main__":
    diag = PerformanceDiagnostic()
    diag.run_all_diagnostics()