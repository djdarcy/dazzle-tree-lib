"""Execution planning for DazzleTreeLib.

The ExecutionPlan validates that a TraversalConfig can be satisfied by
a TreeAdapter and coordinates the actual traversal execution.
"""

from typing import Iterator, Tuple, Any, List, Optional, Dict, TYPE_CHECKING
from enum import Enum
from .core.node import TreeNode
from .core.adapter import TreeAdapter
from .core.traverser import TreeTraverser, create_traverser
from .core.collector import (
    DataCollector,
    IdentifierCollector,
    MetadataCollector,
    FullNodeCollector,
    ChildCountCollector,
    PathCollector,
    CustomCollector
)
from .config import TraversalConfig, DataRequirement, TraversalStrategy

# Import AsyncIterator for type hints
try:
    from typing import AsyncIterator
except ImportError:
    from collections.abc import AsyncIterator


class DataCapability(Enum):
    """What data an adapter can provide."""
    IDENTIFIER = "identifier"
    METADATA = "metadata"
    FULL_NODE = "full_node"
    CHILDREN = "children"
    ASYNC = "async"
    MODIFICATION = "modification"


class CapabilityMismatchError(Exception):
    """Raised when configuration requirements can't be met by adapter."""
    pass


class ExecutionPlan:
    """Validated execution plan for tree traversal.
    
    The ExecutionPlan is the bridge between user intent (TraversalConfig)
    and execution. It validates that the adapter can satisfy the config
    requirements and assembles the appropriate components for traversal.
    
    This implements the "Execution Plan" pattern that validates compatibility
    before any filesystem/tree operations begin.
    """
    
    def __init__(self, config: TraversalConfig, adapter: TreeAdapter):
        """Create and validate an execution plan.
        
        Args:
            config: User's traversal configuration
            adapter: Tree adapter for the specific tree type
            
        Raises:
            CapabilityMismatchError: If adapter can't satisfy config
        """
        self.config = config
        self.adapter = adapter
        
        # Validate configuration
        config_errors = config.validate()
        if config_errors:
            raise CapabilityMismatchError(
                f"Invalid configuration: {'; '.join(config_errors)}"
            )
        
        # Validate adapter capabilities
        capability_issues = self._validate_capabilities()
        if capability_issues:
            raise CapabilityMismatchError(
                f"Adapter limitations: {'; '.join(capability_issues)}"
            )
        
        # Select components
        self.traverser = self._select_traverser()
        self.collector = self._select_collector()
        self.cache = self._setup_cache()
        
        # Track execution state
        self.nodes_processed = 0
        self.errors_encountered = []
    
    def _validate_capabilities(self) -> List[str]:
        """Validate adapter can satisfy configuration requirements.
        
        Returns:
            List of capability issues (empty if all satisfied)
        """
        issues = []
        
        # Check data requirements
        if self.config.data_requirements == DataRequirement.FULL_NODE:
            if not self.adapter.supports_full_data():
                issues.append(
                    "Adapter cannot provide full node data as required"
                )
        
        # Check if children access is needed
        if self.config.data_requirements == DataRequirement.CHILDREN_COUNT:
            # All adapters should support basic children iteration
            pass
        
        # Check async requirements
        if self.config.performance.parallel and not self.adapter.supports_async():
            issues.append(
                "Parallel processing requested but adapter doesn't support async"
            )
        
        # Check modification requirements (future feature)
        # if self.config.enable_modification and not self.adapter.supports_modification():
        #     issues.append("Tree modification requested but adapter doesn't support it")
        
        # Check memory constraints vs estimated size
        if self.config.performance.max_memory_mb is not None:
            # This is a soft check - we'll monitor during execution
            pass
        
        return issues
    
    def _select_traverser(self) -> TreeTraverser:
        """Select appropriate traverser based on configuration.
        
        Returns:
            TreeTraverser instance
        """
        if self.config.strategy == TraversalStrategy.CUSTOM:
            if self.config.custom_traverser is None:
                raise ValueError("Custom traverser not provided")
            return self.config.custom_traverser
        
        # Map strategy to traverser
        strategy_map = {
            TraversalStrategy.BREADTH_FIRST: "bfs",
            TraversalStrategy.DEPTH_FIRST_PRE: "dfs_pre",
            TraversalStrategy.DEPTH_FIRST_POST: "dfs_post",
            TraversalStrategy.LEVEL_ORDER: "level"
        }
        
        strategy_name = strategy_map[self.config.strategy]
        return create_traverser(strategy_name, self.adapter)
    
    def _select_collector(self) -> DataCollector:
        """Select appropriate data collector based on requirements.
        
        Returns:
            DataCollector instance
        """
        if self.config.data_requirements == DataRequirement.CUSTOM:
            if self.config.custom_collector is None:
                raise ValueError("Custom collector not provided")
            return self.config.custom_collector
        
        # Map requirements to collectors
        collector_map = {
            DataRequirement.IDENTIFIER_ONLY: IdentifierCollector,
            DataRequirement.METADATA: MetadataCollector,
            DataRequirement.FULL_NODE: FullNodeCollector,
            DataRequirement.CHILDREN_COUNT: ChildCountCollector,
            DataRequirement.PATH: PathCollector,
        }
        
        collector_class = collector_map[self.config.data_requirements]
        return collector_class(self.adapter)
    
    def _setup_cache(self) -> Optional[Any]:
        """Setup caching strategy if configured.
        
        Returns:
            Cache instance or None
        """
        # TODO: Implement caching strategies
        # For now, return None (no caching)
        return None
    
    def _check_limits(self) -> bool:
        """Check if execution limits have been exceeded.
        
        Returns:
            True if we should continue, False if limits exceeded
        """
        # Check node limit
        if not self.config.performance.check_node_limit(self.nodes_processed):
            return False
        
        # TODO: Check memory limit
        # if not self.config.performance.check_memory_limit(current_memory):
        #     return False
        
        return True
    
    def _handle_error(self, node: TreeNode, error: Exception) -> None:
        """Handle an error during traversal.
        
        Args:
            node: Node where error occurred
            error: The exception that was raised
        """
        self.errors_encountered.append((node.identifier(), str(error)))
        
        # Call user's error handler if provided
        if self.config.on_error:
            self.config.on_error(node, error)
        
        # Raise if not skipping errors
        if not self.config.skip_errors:
            raise
    
    def _report_progress(self) -> None:
        """Report progress if callback configured."""
        if self.config.progress_callback:
            if self.nodes_processed % self.config.progress_interval == 0:
                # TODO: Estimate total nodes if possible
                self.config.progress_callback(self.nodes_processed, None)
    
    def execute(self, root: TreeNode) -> Iterator[Tuple[TreeNode, Any]]:
        """Execute the traversal plan.
        
        This is the main entry point for traversal execution.
        It coordinates the traverser, collector, filters, and
        other components according to the configuration.
        
        Args:
            root: Root node to start traversal from
            
        Yields:
            Tuples of (node, collected_data)
        """
        # Reset execution state
        self.nodes_processed = 0
        self.errors_encountered = []
        
        # Start traversal
        for node, depth in self.traverser.traverse(
            root,
            max_depth=self.config.depth.max_depth,
            min_depth=self.config.depth.min_depth
        ):
            try:
                # Check if we should process this node
                if not self.config.filter.should_include(node):
                    continue
                
                # Check depth filter
                if not self.config.depth.should_yield(depth):
                    continue
                
                # Collect data
                data = self.collector.collect(node, depth)
                
                # Update counters
                self.nodes_processed += 1
                
                # Check limits
                if not self._check_limits():
                    break
                
                # Report progress
                self._report_progress()
                
                # Yield result
                yield (node, data)
                
            except Exception as e:
                self._handle_error(node, e)
    
    async def execute_async(self, root: TreeNode) -> AsyncIterator[Tuple[TreeNode, Any]]:
        """Execute traversal asynchronously.
        
        This is for future implementation when async support is added.
        
        Args:
            root: Root node to start traversal from
            
        Yields:
            Tuples of (node, collected_data)
            
        Raises:
            NotImplementedError: Async execution not yet implemented
        """
        raise NotImplementedError("Async execution not yet implemented")
    
    def estimate_work(self, root: TreeNode) -> Dict[str, Any]:
        """Estimate the work required for traversal.
        
        Useful for progress reporting and resource planning.
        
        Args:
            root: Root node to start traversal from
            
        Returns:
            Dictionary with estimates (nodes, memory, time, etc.)
        """
        estimates = {
            'estimated_nodes': None,
            'estimated_memory_mb': None,
            'estimated_time_seconds': None,
            'can_complete': True
        }
        
        # Try to get node count estimate from adapter
        node_estimate = self.adapter.estimated_size(root)
        if node_estimate is not None:
            estimates['estimated_nodes'] = node_estimate
            
            # Rough memory estimate based on data requirements
            bytes_per_node = {
                DataRequirement.IDENTIFIER_ONLY: 50,
                DataRequirement.METADATA: 200,
                DataRequirement.FULL_NODE: 1000,
                DataRequirement.CHILDREN_COUNT: 100,
                DataRequirement.PATH: 150,
            }.get(self.config.data_requirements, 200)
            
            estimates['estimated_memory_mb'] = (
                node_estimate * bytes_per_node / 1_000_000
            )
            
            # Check if we can complete within memory limit
            if self.config.performance.max_memory_mb is not None:
                if estimates['estimated_memory_mb'] > self.config.performance.max_memory_mb:
                    estimates['can_complete'] = False
        
        return estimates
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of execution plan.
        
        Useful for debugging and logging.
        
        Returns:
            Dictionary with plan details
        """
        return {
            'strategy': self.config.strategy.value,
            'data_requirements': self.config.data_requirements.value,
            'max_depth': self.config.depth.max_depth,
            'min_depth': self.config.depth.min_depth,
            'lazy_evaluation': self.config.performance.lazy_evaluation,
            'cache_strategy': self.config.cache_strategy.value,
            'adapter': self.adapter.__class__.__name__,
            'traverser': self.traverser.__class__.__name__,
            'collector': self.collector.__class__.__name__,
        }