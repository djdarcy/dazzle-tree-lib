#!/usr/bin/env python
"""
Simple CI Tester for DazzleTreeLib
===================================

Tests if your code will pass GitHub Actions CI/CD.
Focuses on the critical checks that actually fail in CI.

Usage:
    python scripts/test-ci.py
"""

import subprocess
import sys
from pathlib import Path

def run_command(cmd, description, critical=True):
    """Run a command and return True if it succeeds."""
    print(f"\n[Testing] {description}...")
    print(f"  Command: {cmd}")

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"  PASSED")
        return True
    else:
        if critical:
            print(f"  FAILED - This will fail in CI!")
            if result.stderr:
                print(f"  Error: {result.stderr[:500]}")
        else:
            print(f"  WARNING - Non-critical issue")
        return False

def main():
    print("=" * 60)
    print("CI/CD LOCAL TESTER")
    print("=" * 60)
    print("\nThis tests the critical things that fail in GitHub Actions")

    project_root = Path(__file__).parent.parent
    all_passed = True

    # Test 1: Can we import the package?
    # This catches missing dependencies like cachetools
    if not run_command(
        'python -c "import dazzletreelib"',
        "Basic import test",
        critical=True
    ):
        print("\n  Fix: Check if all dependencies are in pyproject.toml")
        all_passed = False

    # Test 2: Do the tests run?
    # This is what actually runs in CI
    if not run_command(
        'python run_tests.py',
        "Run fast tests (what CI runs)",
        critical=True
    ):
        print("\n  Fix: Debug the failing tests")
        all_passed = False

    # Test 3: Any Python syntax errors?
    # CI will fail on these
    try:
        import flake8
        if not run_command(
            'flake8 dazzletreelib tests --count --select=E9,F63,F7,F82 --show-source',
            "Check for Python syntax errors",
            critical=True
        ):
            print("\n  Fix: Fix the syntax errors shown above")
            all_passed = False
    except ImportError:
        print("\n[Skipped] Flake8 not installed (pip install flake8 to enable)")

    # Test 4: Can we build the package?
    # This ensures pyproject.toml is valid
    if not run_command(
        'python -m build --version > nul 2>&1',
        "Check if build tool is available",
        critical=False
    ):
        print("  Build tool not installed, skipping build test")
    else:
        if not run_command(
            'python -m build',
            "Build package",
            critical=True
        ):
            print("\n  Fix: Check pyproject.toml for errors")
            all_passed = False

    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("SUCCESS: Your code should pass GitHub CI/CD!")
        print("\nYou can safely commit and push.")
    else:
        print("FAILURE: Fix the issues above before pushing to GitHub")
        print("\nThis will save you from failed CI builds.")
    print("=" * 60)

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())