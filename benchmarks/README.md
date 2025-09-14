# DazzleTreeLib Benchmarks

This directory contains performance benchmarks for DazzleTreeLib.

## Structure

- **Public benchmarks** (committed to repo):
  - `compare_file_search.py` - Compares DazzleTreeLib against native Python approaches
  - Other benchmark scripts that demonstrate library performance

- **Private benchmarks** (`private/` subdirectory - gitignored):
  - Temporary diagnostic reports
  - Test run artifacts
  - Performance measurement JSON files
  - Local benchmark results

## Running Benchmarks

```bash
# Run file search comparison
python benchmarks/compare_file_search.py

# Results from diagnostic tools will be saved to benchmarks/private/
```

## Note

The `private/` subdirectory is automatically excluded from version control. Use it for:
- Temporary benchmark results
- Diagnostic JSON reports
- Local performance testing artifacts
- Any benchmark data that shouldn't be committed