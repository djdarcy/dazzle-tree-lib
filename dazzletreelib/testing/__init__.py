"""Testing utilities for DazzleTreeLib consumers."""

from .fixtures import CacheTestHelper
from .fixtures import CacheTestHelper as TestableCache  # Backward compatibility

__all__ = ['CacheTestHelper', 'TestableCache']