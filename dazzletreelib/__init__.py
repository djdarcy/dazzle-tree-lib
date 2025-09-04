"""DazzleTreeLib - Universal Tree Traversal Library.

DazzleTreeLib provides a generic, extensible framework for traversing and operating on
any tree structure - filesystem, XML, JSON, databases, or custom data structures.

Choose your implementation:
━━━━━━━━━━━━━━━━━━━━━━━━━━
Synchronous:
    from dazzletreelib.sync import traverse_tree
    
Asynchronous:
    from dazzletreelib.aio import traverse_tree_async
━━━━━━━━━━━━━━━━━━━━━━━━━━

Both implementations share the same concepts but are optimized for their
respective execution models. Pick the one that fits your application.
"""

__version__ = "0.9.3"  # Added adapter introspection methods for testing/debugging

# Re-export submodules for convenient access
from . import sync
from . import aio

# Users must explicitly choose their implementation
__all__ = [
    "__version__",
    "sync",
    "aio",
]
