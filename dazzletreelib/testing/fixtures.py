"""Test fixtures for DazzleTreeLib consumers.

These fixtures provide controlled access to internal state for testing purposes
without exposing implementation details as part of the public API.
"""

from typing import Dict, Any, Optional
from pathlib import Path
from ..aio.adapters.cache_completeness_adapter import CacheCompleteness


class TestableCache:
    """Public test fixture for cache verification.
    
    This class provides a stable testing interface for verifying cache behavior
    without exposing internal implementation details. It's designed for use in
    test suites of projects that consume DazzleTreeLib.
    
    Example:
        scanner = FolderScanner(use_cache=True)
        testable = TestableCache(scanner.cache)
        
        # Verify cache behavior
        summary = testable.get_summary()
        assert summary['total_entries'] > 0
        assert testable.was_path_cached(some_path)
    """
    
    def __init__(self, cache_adapter):
        """Initialize with a cache adapter from FolderScanner.
        
        Args:
            cache_adapter: The cache adapter from scanner.cache
        """
        self._adapter = cache_adapter
    
    def get_summary(self) -> Dict[str, Any]:
        """Returns high-level cache state for testing.
        
        Returns:
            Dictionary containing:
            - total_entries: Total number of cached paths
            - shallow_count: Paths scanned to depth 1
            - partial_count: Paths scanned to depths 2-5
            - complete_count: Fully scanned paths
            - has_cache: Whether cache exists and is accessible
        """
        # Check for CompletenessAwareCacheAdapter's cache
        if hasattr(self._adapter, 'cache'):
            cache = self._adapter.cache
            # If cache has CacheEntry objects with completeness
            if cache and len(cache) > 0:
                first_value = next(iter(cache.values()), None)
                if first_value and hasattr(first_value, 'completeness'):
                    return {
                        'total_entries': len(cache),
                        'shallow_count': sum(1 for e in cache.values() 
                                           if e.completeness == CacheCompleteness.SHALLOW),
                        'partial_count': sum(1 for e in cache.values()
                                           if CacheCompleteness.PARTIAL_2 <= e.completeness <= CacheCompleteness.PARTIAL_5),
                        'complete_count': sum(1 for e in cache.values()
                                            if e.completeness == CacheCompleteness.COMPLETE),
                        'has_cache': True
                    }
            # Basic cache without completeness tracking
            return {
                'total_entries': len(cache),
                'shallow_count': 0,
                'partial_count': 0,
                'complete_count': 0,
                'has_cache': True
            }
        
        # Check for CachingTreeAdapter's _cache
        if hasattr(self._adapter, '_cache'):
            cache = self._adapter._cache
            return {
                'total_entries': len(cache),
                'shallow_count': 0,  # TTLCache doesn't track completeness
                'partial_count': 0,
                'complete_count': 0,
                'has_cache': True
            }
        
        return {
            'total_entries': 0,
            'shallow_count': 0,
            'partial_count': 0,
            'complete_count': 0,
            'has_cache': False
        }
    
    def was_path_cached(self, path: Path) -> bool:
        """Check if specific path is in cache.
        
        Args:
            path: Path to check for cache presence
            
        Returns:
            True if path is cached, False otherwise
        """
        if not hasattr(self._adapter, 'cache'):
            return False
        # Cache uses string keys
        path_str = str(path)
        return path_str in self._adapter.cache
    
    def get_completeness(self, path: Path) -> Optional[CacheCompleteness]:
        """Get completeness level for a specific path.
        
        Args:
            path: Path to check
            
        Returns:
            CacheCompleteness level or None if not cached
        """
        if not hasattr(self._adapter, 'cache'):
            return None
        # Cache uses string keys
        path_str = str(path)
        if path_str not in self._adapter.cache:
            return None
        return self._adapter.cache[path_str].completeness
    
    def has_partial_depth(self, path: Path, expected_depth: int) -> bool:
        """Check if path has expected partial depth level.
        
        Args:
            path: Path to check
            expected_depth: Expected depth (2-5 for PARTIAL_2-5)
            
        Returns:
            True if path has the expected partial depth
        """
        completeness = self.get_completeness(path)
        if completeness is None:
            return False
        
        # Map depth to completeness enum
        if expected_depth == 1:
            return completeness == CacheCompleteness.SHALLOW
        elif 2 <= expected_depth <= 5:
            # PARTIAL_2 = 2, PARTIAL_3 = 3, etc.
            return completeness == expected_depth
        elif expected_depth >= 6:
            # Anything deeper than 5 should be COMPLETE
            return completeness == CacheCompleteness.COMPLETE
        return False
    
    def verify_cache_reuse(self, path: Path) -> bool:
        """Verify that a path is available for cache reuse.
        
        Args:
            path: Path to check for reusability
            
        Returns:
            True if path is cached and can be reused
        """
        return self.was_path_cached(path) and self.get_completeness(path) != CacheCompleteness.NONE