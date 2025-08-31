"""Configuration system for DazzleTreeLib.

This module defines how users specify their traversal requirements,
including what data they need, how to filter nodes, and performance constraints.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Set, Any, Dict, List


class DataRequirement(Enum):
    """Specifies what data is needed from nodes.
    
    Used to optimize traversal and memory usage by only
    collecting what's actually needed.
    """
    IDENTIFIER_ONLY = "identifier"      # Just node IDs (most efficient)
    METADATA = "metadata"                # Basic metadata
    CHILDREN_COUNT = "children_count"   # Number of immediate children
    FULL_NODE = "full"                  # Complete node objects
    PATH = "path"                        # Full path from root
    CUSTOM = "custom"                    # User-defined collection


class TraversalStrategy(Enum):
    """How to traverse the tree.
    
    Different strategies are optimal for different use cases.
    """
    BREADTH_FIRST = "bfs"           # Level by level
    DEPTH_FIRST_PRE = "dfs_pre"     # Parent before children
    DEPTH_FIRST_POST = "dfs_post"   # Children before parent
    LEVEL_ORDER = "level"           # Grouped by level
    CUSTOM = "custom"               # User-defined traverser


class CacheStrategy(Enum):
    """How to handle caching during traversal."""
    NONE = "none"               # No caching
    MEMORY = "memory"           # In-memory cache
    DISK = "disk"              # Disk-based cache
    SMART = "smart"            # Adaptive based on size
    CUSTOM = "custom"          # User-defined strategy


class CacheCompleteness(Enum):
    """How complete is cached data for a node/subtree.
    
    Used to track what we know about cached entries and
    whether they need to be refreshed or upgraded.
    """
    NONE = 0            # No data cached
    IDENTIFIER = 1      # Just the ID is cached
    METADATA = 2        # Basic metadata cached
    SHALLOW = 3         # Immediate children only
    PARTIAL = 4         # Some descendants cached
    COMPLETE = 5        # All descendants cached


@dataclass
class FilterConfig:
    """Configuration for filtering nodes during traversal."""
    
    # Path-based filtering
    include_patterns: Optional[Set[str]] = None  # Glob patterns to include
    exclude_patterns: Optional[Set[str]] = None  # Glob patterns to exclude
    
    # Custom filter functions
    include_filter: Optional[Callable[[Any], bool]] = None  # Include predicate
    exclude_filter: Optional[Callable[[Any], bool]] = None  # Exclude predicate
    
    # Pruning behavior
    prune_on_exclude: bool = True  # Don't traverse excluded branches
    
    def should_include(self, node) -> bool:
        """Check if a node should be included based on filters.
        
        Args:
            node: Node to check
            
        Returns:
            True if node passes all filters
        """
        # Check exclude filter first (exclusion takes precedence)
        if self.exclude_filter and self.exclude_filter(node):
            return False
        
        # Check include filter if present
        if self.include_filter:
            return self.include_filter(node)
        
        # Default to including if no filters specified
        return True
    
    def should_explore_children(self, node) -> bool:
        """Check if children of excluded node should be explored.
        
        Args:
            node: Node to check
            
        Returns:
            True if children should be explored
        """
        if not self.prune_on_exclude:
            return True  # Always explore if pruning disabled
        
        # Only explore if node is included
        return self.should_include(node)


@dataclass
class DepthConfig:
    """Configuration for depth-based filtering."""
    
    min_depth: int = 0                          # Minimum depth to yield
    max_depth: Optional[int] = None            # Maximum depth to traverse
    specific_depths: Optional[Set[int]] = None  # Only these specific depths
    
    def should_yield(self, depth: int) -> bool:
        """Check if nodes at this depth should be yielded.
        
        Args:
            depth: Current depth
            
        Returns:
            True if depth is within configured range
        """
        # Check specific depths first
        if self.specific_depths is not None:
            return depth in self.specific_depths
        
        # Check range
        if depth < self.min_depth:
            return False
        if self.max_depth is not None and depth > self.max_depth:
            return False
        
        return True
    
    def should_explore(self, depth: int) -> bool:
        """Check if children at this depth should be explored.
        
        Args:
            depth: Current depth
            
        Returns:
            True if we should go deeper
        """
        # Always explore if we have specific depths beyond current
        if self.specific_depths is not None:
            return any(d > depth for d in self.specific_depths)
        
        # Check max depth
        if self.max_depth is not None:
            return depth < self.max_depth
        
        return True  # No limit


@dataclass
class PerformanceConfig:
    """Configuration for performance and resource management."""
    
    max_memory_mb: Optional[int] = None        # Memory limit in MB
    max_nodes: Optional[int] = None           # Maximum nodes to process
    lazy_evaluation: bool = True              # Use iterators vs lists
    batch_size: Optional[int] = None          # Nodes per batch (for batching)
    parallel: bool = False                    # Enable parallel processing
    num_workers: Optional[int] = None         # Number of parallel workers
    timeout_seconds: Optional[float] = None   # Timeout for traversal
    
    def check_memory_limit(self, current_mb: float) -> bool:
        """Check if memory limit exceeded.
        
        Args:
            current_mb: Current memory usage in MB
            
        Returns:
            True if within limits or no limit set
        """
        if self.max_memory_mb is None:
            return True
        return current_mb <= self.max_memory_mb
    
    def check_node_limit(self, node_count: int) -> bool:
        """Check if node limit exceeded.
        
        Args:
            node_count: Number of nodes processed
            
        Returns:
            True if within limits or no limit set
        """
        if self.max_nodes is None:
            return True
        return node_count <= self.max_nodes


@dataclass
class TraversalConfig:
    """Complete configuration for tree traversal.
    
    This is the primary way users specify what they want from a traversal.
    The ExecutionPlan will validate this configuration against the
    capabilities of the TreeAdapter.
    """
    
    # Traversal algorithm
    strategy: TraversalStrategy = TraversalStrategy.BREADTH_FIRST
    custom_traverser: Optional[Any] = None  # Custom traverser instance
    
    # Depth control
    depth: DepthConfig = field(default_factory=DepthConfig)
    
    # Node filtering
    filter: FilterConfig = field(default_factory=FilterConfig)
    
    # Data collection
    data_requirements: DataRequirement = DataRequirement.METADATA
    custom_collector: Optional[Any] = None  # Custom collector instance
    
    # Performance
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    
    # Caching
    cache_strategy: CacheStrategy = CacheStrategy.NONE
    custom_cache: Optional[Any] = None  # Custom cache instance
    
    # Error handling
    on_error: Optional[Callable[[Any, Exception], None]] = None
    skip_errors: bool = True  # Continue on errors vs fail fast
    
    # Progress reporting
    progress_callback: Optional[Callable[[int, Optional[int]], None]] = None
    progress_interval: int = 100  # Report every N nodes
    
    # Convenience constructors for common configurations
    
    @classmethod
    def shallow_scan(cls, max_depth: int = 1) -> 'TraversalConfig':
        """Create config for shallow scanning.
        
        Args:
            max_depth: How deep to scan (default 1 = immediate children only)
            
        Returns:
            TraversalConfig for shallow scanning
        """
        return cls(
            strategy=TraversalStrategy.BREADTH_FIRST,
            depth=DepthConfig(max_depth=max_depth),
            data_requirements=DataRequirement.METADATA,
            performance=PerformanceConfig(lazy_evaluation=True)
        )
    
    @classmethod
    def deep_scan(cls, data_requirement: DataRequirement = DataRequirement.METADATA) -> 'TraversalConfig':
        """Create config for deep scanning.
        
        Args:
            data_requirement: What data to collect
            
        Returns:
            TraversalConfig for deep scanning
        """
        return cls(
            strategy=TraversalStrategy.DEPTH_FIRST_POST,  # Good for aggregation
            data_requirements=data_requirement,
            performance=PerformanceConfig(lazy_evaluation=True),
            cache_strategy=CacheStrategy.SMART  # Use caching for deep scans
        )
    
    @classmethod
    def memory_efficient(cls, max_memory_mb: int = 100) -> 'TraversalConfig':
        """Create config optimized for memory efficiency.
        
        Args:
            max_memory_mb: Memory limit in MB
            
        Returns:
            TraversalConfig for memory-efficient scanning
        """
        return cls(
            strategy=TraversalStrategy.DEPTH_FIRST_PRE,  # Less memory than BFS
            data_requirements=DataRequirement.IDENTIFIER_ONLY,
            performance=PerformanceConfig(
                max_memory_mb=max_memory_mb,
                lazy_evaluation=True,
                batch_size=1000
            ),
            cache_strategy=CacheStrategy.DISK  # Use disk for large trees
        )
    
    def validate(self) -> List[str]:
        """Validate configuration for consistency.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check depth configuration
        if self.depth.min_depth < 0:
            errors.append("min_depth cannot be negative")
        
        if self.depth.max_depth is not None:
            if self.depth.max_depth < 0:
                errors.append("max_depth cannot be negative")
            if self.depth.max_depth < self.depth.min_depth:
                errors.append("max_depth cannot be less than min_depth")
        
        # Check performance configuration
        if self.performance.max_memory_mb is not None and self.performance.max_memory_mb <= 0:
            errors.append("max_memory_mb must be positive")
        
        if self.performance.max_nodes is not None and self.performance.max_nodes <= 0:
            errors.append("max_nodes must be positive")
        
        if self.performance.num_workers is not None and self.performance.num_workers <= 0:
            errors.append("num_workers must be positive")
        
        # Check custom components
        if self.strategy == TraversalStrategy.CUSTOM and self.custom_traverser is None:
            errors.append("custom_traverser required when strategy is CUSTOM")
        
        if self.data_requirements == DataRequirement.CUSTOM and self.custom_collector is None:
            errors.append("custom_collector required when data_requirements is CUSTOM")
        
        if self.cache_strategy == CacheStrategy.CUSTOM and self.custom_cache is None:
            errors.append("custom_cache required when cache_strategy is CUSTOM")
        
        return errors