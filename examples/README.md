# DazzleTreeLib Examples

This directory contains working examples demonstrating various features and use cases of DazzleTreeLib.

## Available Examples

### Basic Examples

1. **[basic_async.py](basic_async.py)** - Simple async traversal with file size filtering
   - Demonstrates basic async tree traversal
   - Shows how to filter large files
   - Handles file metadata asynchronously

2. **[sync_vs_async.py](sync_vs_async.py)** - Performance comparison between sync and async
   - Side-by-side performance comparison
   - Real speedup measurements
   - Shows parallel processing benefits

3. **[folder_datetime_fix.py](folder_datetime_fix.py)** - Real-world directory timestamp fixer
   - Depth-first post-order traversal
   - Directory timestamp manipulation
   - Production use case example

### Custom Adapters

4. **[git_tree_adapter.py](adapters/git_tree_adapter.py)** - Complete Git repository adapter
   - Shows both sync and async implementations
   - Demonstrates all adapter concepts
   - Includes performance comparison

## Running the Examples

### Basic Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/DazzleTreeLib.git
cd DazzleTreeLib

# Install the library
pip install -e .

# Run an example
python examples/basic_async.py /path/to/directory
```

### Example: Basic Async Traversal

```bash
$ python examples/basic_async.py /home/user/projects

DazzleTreeLib - Basic Async Traversal Example
==================================================
Traversing: /home/user/projects
--------------------------------------------------

Traversal Summary:
  Directories: 2,341
  Files: 8,547
  Total Size: 156.3 MB

Large Files (>1MB):
  12.5 MB: database.db
  8.3 MB: video.mp4
  5.2 MB: dataset.csv
```

### Example: Performance Comparison

```bash
$ python examples/sync_vs_async.py /home/user/documents

DazzleTreeLib - Sync vs Async Performance Comparison
============================================================
Test Directory: /home/user/documents
------------------------------------------------------------

1. Synchronous Traversal:
   Files: 5,234, Dirs: 1,456
   Time: 3.245 seconds

2. Asynchronous Traversal:
   Files: 5,234, Dirs: 1,456
   Time: 0.987 seconds

   >>> Speedup: 3.29x faster!

3. Parallel Async Traversal (multiple trees):
   Processing 5 directories in parallel...
   Sequential time: 8.123 seconds
   Parallel time: 2.189 seconds
   >>> Parallel speedup: 3.71x faster!
```

### Example: Folder DateTime Fix

```bash
$ python examples/folder_datetime_fix.py /backup/photos --live

DazzleTreeLib - Folder DateTime Fix Example
============================================================
Scanning directory tree: /backup/photos
Mode: LIVE UPDATE
------------------------------------------------------------
Found 523 directories to process
------------------------------------------------------------
  Updated: /backup/photos/2023
  Updated: /backup/photos/2023/January
  Updated: /backup/photos/2023/February
  ...

============================================================
Summary:
  Directories scanned: 523
  Directories updated: 187
  Directories skipped: 336
  Errors encountered:  0
  Time elapsed: 1.23 seconds
```

## Creating Your Own Examples

### Template for New Examples

```python
#!/usr/bin/env python3
"""
Description of what your example demonstrates.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from dazzletreelib.aio import traverse_tree_async

async def main():
    """Main function for your example."""
    if len(sys.argv) < 2:
        print("Usage: python your_example.py <directory>")
        sys.exit(1)
    
    root_path = Path(sys.argv[1])
    
    # Your example code here
    async for node in traverse_tree_async(root_path):
        # Process each node
        pass

if __name__ == "__main__":
    asyncio.run(main())
```

## Example Categories

### Performance Examples
- Benchmarking different configurations
- Comparing sync vs async
- Testing parameter tuning

### Use Case Examples
- File system operations
- Directory management
- Search and filtering
- Data collection

### Adapter Examples
- Custom tree structures
- Database hierarchies
- API traversal
- Cloud storage trees

## Contributing Examples

To contribute a new example:

1. Create your example in the appropriate directory
2. Include comprehensive comments
3. Add error handling
4. Document expected output
5. Submit a pull request

See the [Contributing Guide](../CONTRIBUTING.md) for more details.