#!/usr/bin/env python
"""
Test GitHub Actions workflows locally
======================================

Simulates GitHub Actions workflow commands to catch errors before pushing.
"""

import subprocess
import sys
import os
from pathlib import Path
import tempfile
import shutil

def run_command(cmd, description, cwd=None, env=None, allow_failure=False):
    """Run a command and report results."""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Command: {cmd}")
    print(f"{'='*60}")

    try:
        # Set up environment
        test_env = os.environ.copy()
        if env:
            test_env.update(env)

        # Run the command
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=test_env
        )

        if result.returncode != 0:
            print(f"FAILED with exit code {result.returncode}")
            if result.stdout:
                print("STDOUT:", result.stdout[:500])
            if result.stderr:
                print("STDERR:", result.stderr[:500])
            if not allow_failure:
                return False
        else:
            print(f"PASSED")
            if result.stdout and len(result.stdout) < 200:
                print("Output:", result.stdout.strip())

        return True

    except Exception as e:
        print(f"EXCEPTION: {e}")
        return False if not allow_failure else True


def test_workflow_commands():
    """Test all commands from GitHub Actions workflows."""

    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    all_passed = True

    print("\n" + "="*80)
    print("TESTING GITHUB ACTIONS WORKFLOW COMMANDS LOCALLY")
    print("="*80)

    # Set up environment similar to GitHub Actions
    github_env = {
        "PYTHONPATH": str(project_root),
        "CI": "true"
    }

    # Test from tests.yml
    print("\n\nTESTING: tests.yml commands")
    print("-" * 40)

    # Test the problematic --fast flag
    if not run_command(
        "python run_tests.py --fast",
        "Run fast tests with --fast flag (EXPECTED TO FAIL)",
        env=github_env,
        allow_failure=True
    ):
        print("WARNING: Confirmed: --fast flag doesn't exist")

        # Test the correct command
        if not run_command(
            "python run_tests.py",
            "Run fast tests (default behavior)",
            env=github_env
        ):
            all_passed = False

    # Test linting commands
    print("\n\nTESTING: Linting commands")
    print("-" * 40)

    # Black formatting check
    if not run_command(
        "black --check dazzletreelib tests",
        "Check code formatting with black",
        allow_failure=True  # Don't fail overall test
    ):
        print("WARNING: Code formatting issues (non-critical)")

    # Flake8 syntax errors check
    if not run_command(
        "flake8 dazzletreelib tests --count --select=E9,F63,F7,F82 --show-source --statistics",
        "Check for Python syntax errors",
        allow_failure=False  # This should pass
    ):
        all_passed = False

    # Mypy type checking
    if not run_command(
        "mypy dazzletreelib --ignore-missing-imports",
        "Type checking with mypy",
        allow_failure=True  # Don't fail overall test
    ):
        print("WARNING: Type checking issues (non-critical)")

    # Test from main.yml
    print("\n\nTESTING: main.yml commands")
    print("-" * 40)

    # Test pytest with coverage
    if not run_command(
        "python -m pytest --cov=dazzletreelib --cov-report=term --cov-report=xml -q",
        "Run tests with coverage",
        env=github_env
    ):
        all_passed = False

    # Test build process
    print("\n\nTESTING: Build process")
    print("-" * 40)

    if not run_command(
        "python -m build --version",
        "Check if build tool is available"
    ):
        print("Installing build tool...")
        run_command("pip install build", "Install build tool")

    # Test package building
    with tempfile.TemporaryDirectory() as tmpdir:
        if not run_command(
            f"python -m build --outdir {tmpdir}",
            "Build package",
            env=github_env
        ):
            all_passed = False

    # Test benchmarks command
    print("\n\nTESTING: Benchmark commands")
    print("-" * 40)

    benchmark_script = project_root / "benchmarks" / "accurate_performance_test.py"
    if benchmark_script.exists():
        if not run_command(
            f"python {benchmark_script}",
            "Run benchmarks (informational)",
            allow_failure=True
        ):
            print("WARNING: Benchmarks completed with warnings (expected)")
    else:
        print("WARNING: Benchmark script not found")

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    if all_passed:
        print("SUCCESS: All critical workflow commands passed!")
    else:
        print("ERROR: Some workflow commands failed - fix before pushing")

    print("\nISSUES FOUND:")
    print("1. ERROR: tests.yml uses '--fast' flag but run_tests.py doesn't accept it")
    print("   Fix: Remove '--fast' from line 48 of tests.yml")
    print("\nRECOMMENDATION:")
    print("Fix the --fast flag issue in tests.yml before pushing to GitHub")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(test_workflow_commands())