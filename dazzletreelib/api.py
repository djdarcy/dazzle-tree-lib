"""High-level API for DazzleTreeLib.

This module provides simple, functional interfaces for common tree traversal
operations. These functions wrap the more complex object-oriented API for
ease of use in simple cases.
"""

from typing import Iterator, Optional, Callable, Any, Union, Tuple, List, Dict
from .core.node import TreeNode
from .core.adapter import TreeAdapter
from .config import (
    TraversalConfig,
    TraversalStrategy,
    DataRequirement,
    DepthConfig,
    FilterConfig,
    PerformanceConfig
)
from .planning import ExecutionPlan


def traverse_tree(
    root: TreeNode,
    adapter: TreeAdapter,
    strategy: Union[TraversalStrategy, str] = TraversalStrategy.BREADTH_FIRST,
    max_depth: Optional[int] = None,
    min_depth: int = 0,
    include_filter: Optional[Callable[[TreeNode], bool]] = None,
    exclude_filter: Optional[Callable[[TreeNode], bool]] = None,
    data_requirement: DataRequirement = DataRequirement.METADATA,
    lazy: bool = True,
    on_error: Optional[Callable[[TreeNode, Exception], None]] = None,
    **kwargs
) -> Iterator[TreeNode]:
    """Simple interface for tree traversal.
    
    This is the primary high-level function for traversing trees.
    It handles the common case of wanting to iterate over nodes
    without dealing with the complexity of configs and plans.
    
    Args:
        root: Starting node for traversal
        adapter: Tree adapter for the specific tree type
        strategy: Traversal strategy (bfs, dfs_pre, dfs_post, level)
        max_depth: Maximum depth to traverse
        min_depth: Minimum depth before yielding nodes
        include_filter: Function to determine if node should be included
        exclude_filter: Function to determine if node should be excluded
        data_requirement: What data to collect from nodes
        lazy: Use lazy evaluation (iterator) vs eager (list)
        on_error: Error handler callback
        **kwargs: Additional config options
        
    Yields:
        TreeNode instances that match the criteria
        
    Example:
        >>> adapter = FileSystemAdapter()
        >>> root = FileSystemNode(Path("/home/user"))
        >>> for node in traverse_tree(root, adapter, max_depth=2):
        ...     print(node.identifier())
    """
    # Build configuration from parameters
    config = TraversalConfig(
        strategy=_parse_strategy(strategy),
        depth=DepthConfig(
            min_depth=min_depth,
            max_depth=max_depth
        ),
        filter=FilterConfig(
            include_filter=include_filter,
            exclude_filter=exclude_filter
        ),
        data_requirements=data_requirement,
        performance=PerformanceConfig(
            lazy_evaluation=lazy
        ),
        on_error=on_error,
        skip_errors=True if on_error else False
    )
    
    # Apply any additional kwargs to config
    # This allows power users to set advanced options
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    # Create and execute plan
    plan = ExecutionPlan(config, adapter)
    
    # Yield just the nodes (not the collected data)
    for node, _ in plan.execute(root):
        yield node


def collect_tree_data(
    root: TreeNode,
    adapter: TreeAdapter,
    data_requirement: DataRequirement = DataRequirement.METADATA,
    **kwargs
) -> Iterator[Tuple[TreeNode, Any]]:
    """Traverse tree and collect specified data.
    
    Similar to traverse_tree but returns both nodes and collected data.
    
    Args:
        root: Starting node for traversal
        adapter: Tree adapter for the specific tree type
        data_requirement: What data to collect
        **kwargs: Additional traversal options (see traverse_tree)
        
    Yields:
        Tuples of (node, collected_data)
        
    Example:
        >>> adapter = FileSystemAdapter()
        >>> root = FileSystemNode(Path("/home/user"))
        >>> for node, metadata in collect_tree_data(root, adapter):
        ...     print(f"{node.identifier()}: {metadata['size']} bytes")
    """
    # Build configuration
    config_kwargs = kwargs.copy()
    config_kwargs['data_requirement'] = data_requirement
    
    config = _build_config_from_kwargs(**config_kwargs)
    
    # Create and execute plan
    plan = ExecutionPlan(config, adapter)
    
    # Yield nodes with collected data
    yield from plan.execute(root)


def count_nodes(
    root: TreeNode,
    adapter: TreeAdapter,
    **kwargs
) -> int:
    """Count nodes in a tree that match criteria.
    
    Args:
        root: Starting node for traversal
        adapter: Tree adapter for the specific tree type
        **kwargs: Traversal options (see traverse_tree)
        
    Returns:
        Number of nodes that match criteria
        
    Example:
        >>> adapter = FileSystemAdapter()
        >>> root = FileSystemNode(Path("/home/user"))
        >>> count = count_nodes(root, adapter, max_depth=2)
        >>> print(f"Found {count} nodes")
    """
    count = 0
    for _ in traverse_tree(root, adapter, **kwargs):
        count += 1
    return count


def find_nodes(
    root: TreeNode,
    adapter: TreeAdapter,
    predicate: Callable[[TreeNode], bool],
    **kwargs
) -> Iterator[TreeNode]:
    """Find nodes that match a predicate.
    
    Args:
        root: Starting node for traversal
        adapter: Tree adapter for the specific tree type
        predicate: Function that returns True for matching nodes
        **kwargs: Traversal options (see traverse_tree)
        
    Yields:
        Nodes that match the predicate
        
    Example:
        >>> adapter = FileSystemAdapter()
        >>> root = FileSystemNode(Path("/home/user"))
        >>> # Find all directories
        >>> for node in find_nodes(root, adapter, lambda n: n.metadata()['is_dir']):
        ...     print(node.identifier())
    """
    kwargs['include_filter'] = predicate
    yield from traverse_tree(root, adapter, **kwargs)


def get_tree_paths(
    root: TreeNode,
    adapter: TreeAdapter,
    **kwargs
) -> Iterator[List[str]]:
    """Get paths from root to each node.
    
    Args:
        root: Starting node for traversal
        adapter: Tree adapter for the specific tree type
        **kwargs: Traversal options (see traverse_tree)
        
    Yields:
        Lists of node identifiers forming paths from root
        
    Example:
        >>> adapter = FileSystemAdapter()
        >>> root = FileSystemNode(Path("/home"))
        >>> for path in get_tree_paths(root, adapter, max_depth=2):
        ...     print(" -> ".join(path))
    """
    kwargs['data_requirement'] = DataRequirement.PATH
    
    for node, path_data in collect_tree_data(root, adapter, **kwargs):
        yield path_data


def get_leaf_nodes(
    root: TreeNode,
    adapter: TreeAdapter,
    **kwargs
) -> Iterator[TreeNode]:
    """Get all leaf nodes in a tree.
    
    Args:
        root: Starting node for traversal
        adapter: Tree adapter for the specific tree type
        **kwargs: Traversal options (see traverse_tree)
        
    Yields:
        Leaf nodes (nodes with no children)
        
    Example:
        >>> adapter = FileSystemAdapter()
        >>> root = FileSystemNode(Path("/home/user"))
        >>> for leaf in get_leaf_nodes(root, adapter):
        ...     print(f"Leaf: {leaf.identifier()}")
    """
    for node in traverse_tree(root, adapter, **kwargs):
        if node.is_leaf():
            yield node


def get_tree_stats(
    root: TreeNode,
    adapter: TreeAdapter,
    **kwargs
) -> Dict[str, Any]:
    """Get statistics about a tree.
    
    Args:
        root: Starting node for traversal
        adapter: Tree adapter for the specific tree type
        **kwargs: Traversal options (see traverse_tree)
        
    Returns:
        Dictionary with tree statistics
        
    Example:
        >>> adapter = FileSystemAdapter()
        >>> root = FileSystemNode(Path("/home/user"))
        >>> stats = get_tree_stats(root, adapter)
        >>> print(f"Total nodes: {stats['total_nodes']}")
        >>> print(f"Leaf nodes: {stats['leaf_nodes']}")
    """
    stats = {
        'total_nodes': 0,
        'leaf_nodes': 0,
        'max_depth': 0,
        'depths': {}
    }
    
    for node, depth in collect_tree_data(
        root, adapter,
        data_requirement=DataRequirement.IDENTIFIER_ONLY,
        **kwargs
    ):
        stats['total_nodes'] += 1
        
        if node.is_leaf():
            stats['leaf_nodes'] += 1
        
        stats['max_depth'] = max(stats['max_depth'], depth)
        
        if depth not in stats['depths']:
            stats['depths'][depth] = 0
        stats['depths'][depth] += 1
    
    stats['internal_nodes'] = stats['total_nodes'] - stats['leaf_nodes']
    stats['average_branching'] = (
        stats['internal_nodes'] / stats['total_nodes']
        if stats['total_nodes'] > 0 else 0
    )
    
    return stats


# Helper functions

def _parse_strategy(strategy: Union[TraversalStrategy, str]) -> TraversalStrategy:
    """Parse strategy from string or enum.
    
    Args:
        strategy: Strategy as enum or string
        
    Returns:
        TraversalStrategy enum value
    """
    if isinstance(strategy, TraversalStrategy):
        return strategy
    
    # Map string names to enum values
    strategy_map = {
        'bfs': TraversalStrategy.BREADTH_FIRST,
        'breadth_first': TraversalStrategy.BREADTH_FIRST,
        'dfs': TraversalStrategy.DEPTH_FIRST_PRE,
        'dfs_pre': TraversalStrategy.DEPTH_FIRST_PRE,
        'depth_first_pre': TraversalStrategy.DEPTH_FIRST_PRE,
        'dfs_post': TraversalStrategy.DEPTH_FIRST_POST,
        'depth_first_post': TraversalStrategy.DEPTH_FIRST_POST,
        'level': TraversalStrategy.LEVEL_ORDER,
        'level_order': TraversalStrategy.LEVEL_ORDER,
    }
    
    strategy_lower = strategy.lower() if isinstance(strategy, str) else str(strategy)
    if strategy_lower in strategy_map:
        return strategy_map[strategy_lower]
    
    raise ValueError(f"Unknown traversal strategy: {strategy}")


def _build_config_from_kwargs(**kwargs) -> TraversalConfig:
    """Build TraversalConfig from keyword arguments.
    
    Args:
        **kwargs: Configuration options
        
    Returns:
        TraversalConfig instance
    """
    config = TraversalConfig()
    
    # Map common kwargs to config attributes
    if 'strategy' in kwargs:
        config.strategy = _parse_strategy(kwargs.pop('strategy'))
    
    if 'max_depth' in kwargs:
        config.depth.max_depth = kwargs.pop('max_depth')
    
    if 'min_depth' in kwargs:
        config.depth.min_depth = kwargs.pop('min_depth')
    
    if 'include_filter' in kwargs:
        config.filter.include_filter = kwargs.pop('include_filter')
    
    if 'exclude_filter' in kwargs:
        config.filter.exclude_filter = kwargs.pop('exclude_filter')
    
    if 'data_requirement' in kwargs:
        config.data_requirements = kwargs.pop('data_requirement')
    
    if 'lazy' in kwargs:
        config.performance.lazy_evaluation = kwargs.pop('lazy')
    
    if 'on_error' in kwargs:
        config.on_error = kwargs.pop('on_error')
        config.skip_errors = True
    
    # Apply any remaining kwargs directly
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    return config