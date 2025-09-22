#!/usr/bin/env python
"""
Download and view coverage reports from GitHub Actions CI runs.

This script downloads coverage report artifacts from recent CI runs,
organizes them by date/run, and optionally opens the report in a browser.

Usage:
    python scripts/get-coverage.py           # Download latest coverage
    python scripts/get-coverage.py --list    # List recent runs with coverage
    python scripts/get-coverage.py --run-id 12345  # Download specific run
    python scripts/get-coverage.py --open    # Download and open in browser
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path


def run_command(cmd, capture_output=True):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=capture_output,
            text=True,
            check=True
        )
        return result.stdout.strip() if capture_output else None
    except subprocess.CalledProcessError as e:
        if capture_output:
            print(f"Error running command: {cmd}")
            print(f"Error output: {e.stderr}")
        return None


def list_recent_runs(limit=10):
    """List recent CI runs that have coverage artifacts."""
    print(f"\nFetching last {limit} CI runs...")

    # Get recent runs in JSON format
    cmd = f"gh run list --limit {limit} --json databaseId,displayTitle,status,conclusion,createdAt,workflowName"
    output = run_command(cmd)

    if not output:
        print("Failed to fetch CI runs. Make sure 'gh' CLI is installed and authenticated.")
        return []

    runs = json.loads(output)
    runs_with_coverage = []

    print("\nChecking for coverage artifacts...")
    for run in runs:
        run_id = run['databaseId']
        # Check if this run has coverage artifacts
        artifact_cmd = f"gh run view {run_id} --json artifacts"
        artifact_output = run_command(artifact_cmd)

        if artifact_output:
            artifacts = json.loads(artifact_output).get('artifacts', [])
            has_coverage = any(a['name'] == 'coverage-report' for a in artifacts)

            if has_coverage:
                runs_with_coverage.append(run)

    return runs_with_coverage


def display_runs(runs):
    """Display runs in a formatted table."""
    if not runs:
        print("\nNo runs with coverage reports found.")
        return

    print("\n" + "=" * 100)
    print(f"{'ID':<12} {'Status':<10} {'Date':<20} {'Title':<45}")
    print("=" * 100)

    for run in runs:
        run_id = run['databaseId']
        status = run['conclusion'] or run['status']
        created = datetime.fromisoformat(run['createdAt'].replace('Z', '+00:00'))
        created_str = created.strftime('%Y-%m-%d %H:%M')
        title = run['displayTitle'][:44]

        # Color code status
        status_display = status
        if status == 'success':
            status_display = f"✓ {status}"
        elif status == 'failure':
            status_display = f"✗ {status}"
        elif status == 'in_progress':
            status_display = f"⟳ {status}"

        print(f"{run_id:<12} {status_display:<10} {created_str:<20} {title:<45}")

    print("=" * 100)


def download_coverage(run_id=None, output_dir=None):
    """Download coverage report from a specific run or the latest run."""

    # Create reports directory
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    # Get run ID if not specified
    if not run_id:
        print("\nFetching latest successful run with coverage...")
        runs = list_recent_runs(limit=5)
        successful_runs = [r for r in runs if r.get('conclusion') == 'success']

        if not successful_runs:
            print("No successful runs with coverage found.")
            return None

        run_id = successful_runs[0]['databaseId']
        print(f"Using latest successful run: {run_id}")

    # Get run details
    cmd = f"gh run view {run_id} --json displayTitle,createdAt"
    output = run_command(cmd)

    if not output:
        print(f"Failed to get details for run {run_id}")
        return None

    run_info = json.loads(output)
    created = datetime.fromisoformat(run_info['createdAt'].replace('Z', '+00:00'))

    # Create output directory
    if not output_dir:
        # Use YYYY-MM-DD__hh-mm-ss format to match our standard naming convention
        dir_name = f"{created.strftime('%Y-%m-%d__%H-%M-%S')}_run-{run_id}"
        output_dir = reports_dir / dir_name
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Download coverage artifact
    print(f"\nDownloading coverage report to {output_dir}...")

    # Change to output directory to download files there
    original_cwd = os.getcwd()
    os.chdir(output_dir)

    try:
        cmd = f"gh run download {run_id} -n coverage-report"
        result = run_command(cmd, capture_output=False)

        # Check if files were downloaded
        html_files = list(output_dir.glob("*.html"))

        if html_files:
            print(f"✓ Downloaded {len(html_files)} coverage files")

            # Create metadata file
            metadata = {
                'run_id': run_id,
                'title': run_info.get('displayTitle', 'Unknown'),
                'created': created.isoformat(),
                'downloaded': datetime.now().isoformat(),
                'files': [f.name for f in html_files]
            }

            metadata_file = output_dir / "metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)

            print(f"✓ Created metadata file")

            return output_dir / "index.html"
        else:
            print("✗ No coverage files found in artifact")
            return None

    finally:
        os.chdir(original_cwd)


def open_coverage_report(report_path):
    """Open coverage report in default browser."""
    if report_path and report_path.exists():
        print(f"\nOpening coverage report in browser...")
        webbrowser.open(f"file://{report_path.absolute()}")
        return True
    else:
        print(f"Coverage report not found: {report_path}")
        return False


def list_local_reports():
    """List locally downloaded coverage reports."""
    reports_dir = Path("reports")

    if not reports_dir.exists():
        print("\nNo local coverage reports found.")
        return []

    reports = []
    for dir_path in sorted(reports_dir.iterdir(), reverse=True):
        if dir_path.is_dir():
            metadata_file = dir_path / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file) as f:
                    metadata = json.load(f)
                    reports.append({
                        'path': dir_path,
                        'metadata': metadata
                    })

    if reports:
        print(f"\n{'Local Coverage Reports':<30}")
        print("=" * 80)
        print(f"{'Directory':<30} {'Date':<20} {'Title':<30}")
        print("-" * 80)

        for report in reports:
            dir_name = report['path'].name
            created = datetime.fromisoformat(report['metadata']['created'])
            created_str = created.strftime('%Y-%m-%d %H:%M')
            title = report['metadata']['title'][:29]

            print(f"{dir_name:<30} {created_str:<20} {title:<30}")

        print("=" * 80)
        print(f"Total: {len(reports)} reports")
    else:
        print("\nNo local coverage reports with metadata found.")

    return reports


def clean_old_reports(keep_last=5):
    """Clean up old coverage reports, keeping only the most recent ones."""
    reports_dir = Path("reports")

    if not reports_dir.exists():
        return

    # Get all report directories with metadata
    reports = []
    for dir_path in reports_dir.iterdir():
        if dir_path.is_dir():
            metadata_file = dir_path / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file) as f:
                    metadata = json.load(f)
                    reports.append((dir_path, metadata))

    # Sort by creation date
    reports.sort(key=lambda x: x[1]['created'], reverse=True)

    # Remove old reports
    if len(reports) > keep_last:
        print(f"\nCleaning up old reports (keeping last {keep_last})...")
        for dir_path, metadata in reports[keep_last:]:
            print(f"  Removing {dir_path.name}")
            shutil.rmtree(dir_path)

        print(f"✓ Removed {len(reports) - keep_last} old reports")


def main():
    parser = argparse.ArgumentParser(
        description="Download and manage coverage reports from GitHub Actions"
    )

    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List recent CI runs with coverage'
    )

    parser.add_argument(
        '--local',
        action='store_true',
        help='List locally downloaded coverage reports'
    )

    parser.add_argument(
        '--run-id', '-r',
        type=int,
        help='Download coverage from specific run ID'
    )

    parser.add_argument(
        '--open', '-o',
        action='store_true',
        help='Open coverage report in browser after downloading'
    )

    parser.add_argument(
        '--clean',
        action='store_true',
        help='Clean up old coverage reports (keeps last 5)'
    )

    parser.add_argument(
        '--keep',
        type=int,
        default=5,
        help='Number of reports to keep when cleaning (default: 5)'
    )

    args = parser.parse_args()

    print("DazzleTreeLib Coverage Report Manager")
    print("=" * 40)

    try:
        # Check if gh CLI is available
        result = run_command("gh --version")
        if not result:
            print("\nError: GitHub CLI (gh) is not installed or not in PATH")
            print("Install from: https://cli.github.com/")
            sys.exit(1)

        # Handle different modes
        if args.list:
            runs = list_recent_runs()
            display_runs(runs)

        elif args.local:
            list_local_reports()

        elif args.clean:
            clean_old_reports(keep_last=args.keep)

        else:
            # Download coverage
            report_path = download_coverage(run_id=args.run_id)

            if report_path:
                print(f"\n✓ Coverage report available at:")
                print(f"  {report_path}")

                if args.open:
                    open_coverage_report(report_path)
                else:
                    print(f"\nTo view the report, open:")
                    print(f"  {report_path}")
            else:
                print("\n✗ Failed to download coverage report")
                sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()