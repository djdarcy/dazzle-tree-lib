"""Test fixtures for DazzleTreeLib consumers.

These fixtures provide controlled access to internal state for testing purposes
without exposing implementation details as part of the public API.
"""

from typing import Dict, Any, Optional
from pathlib import Path
from ..aio.adapters.cache_completeness_adapter import CacheEntry


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
            # If cache has CacheEntry objects with depth
            if cache and len(cache) > 0:
                first_value = next(iter(cache.values()), None)
                if first_value and hasattr(first_value, 'depth'):
                    return {
                        'total_entries': len(cache),
                        'shallow_count': sum(1 for e in cache.values() 
                                           if e.depth == 1),
                        'partial_count': sum(1 for e in cache.values()
                                           if 2 <= e.depth <= 5),
                        'complete_count': sum(1 for e in cache.values()
                                            if e.depth == CacheEntry.COMPLETE_DEPTH),
                        'has_cache': True
                    }
            # Basic cache without depth tracking
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
        # Check if path is in any cache key (keys are now tuples)
        path_str = str(path)
        for key in self._adapter.cache.keys():
            if isinstance(key, tuple) and len(key) >= 4:
                # Key format: (class_id, instance_num, key_type, path, depth)
                if path_str == key[3]:
                    return True
        # Fallback for simple string keys
        return path_str in self._adapter.cache
    
    def get_completeness(self, path: Path) -> Optional[int]:
        """Get completeness level (depth) for a specific path.
        
        Args:
            path: Path to check
            
        Returns:
            Depth level (-1 for complete, 0+ for specific depths) or None if not cached
        """
        if not hasattr(self._adapter, 'cache'):
            return None
        # Need to check all cache keys since they are tuples now
        for key, entry in self._adapter.cache.items():
            if isinstance(key, tuple) and len(key) >= 4:
                # Key format: (class_id, instance_num, key_type, path, depth)
                if str(path) == key[3]:
                    return entry.depth
        return None
    
    def has_partial_depth(self, path: Path, expected_depth: int) -> bool:
        """Check if path has expected partial depth level.
        
        Args:
            path: Path to check
            expected_depth: Expected depth
            
        Returns:
            True if path has the expected partial depth
        """
        actual_depth = self.get_completeness(path)
        if actual_depth is None:
            return False
        
        # Direct depth comparison
        if actual_depth == CacheEntry.COMPLETE_DEPTH:
            # Complete scan satisfies any depth
            return True
        return actual_depth >= expected_depth
    
    def verify_cache_reuse(self, path: Path) -> bool:
        """Verify that a path is available for cache reuse.
        
        Args:
            path: Path to check for reusability
            
        Returns:
            True if path is cached and can be reused
        """
        depth = self.get_completeness(path)
        return depth is not None and depth != 0
    
    def was_node_visited(self, path: Path) -> bool:
        """Check if a node was visited during traversal (node tracking).
        
        This is different from was_path_cached() - it checks the node completeness
        tracker which records ALL visited nodes, not just those whose children
        were fetched.
        
        Args:
            path: Path to check for visitation
            
        Returns:
            True if node was visited during any traversal
        """
        if not hasattr(self._adapter, 'node_completeness'):
            # Fallback to cache check if no node tracking
            return self.was_path_cached(path)
        
        path_str = str(path)
        return path_str in self._adapter.node_completeness
    
    def get_node_depth(self, path: Path) -> Optional[int]:
        """Get the depth to which a node was scanned.
        
        This uses the node completeness tracker to determine how deep
        a specific node was scanned during traversal.
        
        Args:
            path: Path to check
            
        Returns:
            Depth to which node was scanned, or None if not visited
        """
        if not hasattr(self._adapter, 'node_completeness'):
            # Fallback to depth if no node tracking
            depth = self.get_completeness(path)
            if depth is None:
                return None
            # Return depth directly (convert -1 to 999 for backward compat)
            if depth == CacheEntry.COMPLETE_DEPTH:
                return 999
            return depth
        
        path_str = str(path)
        return self._adapter.node_completeness.get(path_str)
    
    def has_node_depth(self, path: Path, expected_depth: int) -> bool:
        """Check if a node was scanned to at least the expected depth.
        
        This is the node-tracking equivalent of has_partial_depth().
        
        Args:
            path: Path to check
            expected_depth: Minimum depth expected
            
        Returns:
            True if node was scanned to at least expected_depth
        """
        actual_depth = self.get_node_depth(path)
        if actual_depth is None:
            return False
        return actual_depth >= expected_depth