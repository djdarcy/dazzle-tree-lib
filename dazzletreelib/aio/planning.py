"""Async execution planning for tree traversal.

This module provides the AsyncExecutionPlan class that orchestrates
traversal, filtering, and data collection operations.
"""

from dataclasses import dataclass
from typing import Optional, Any, AsyncIterator, Callable, Set, Tuple, List
from pathlib import Path

from .core import (
    AsyncTreeNode,
    AsyncTreeAdapter,
    AsyncTreeTraverser,
    AsyncBreadthFirstTraverser,
    AsyncDepthFirstTraverser,
    AsyncDataCollector,
    AsyncMetadataCollector,
)
from .adapters import (
    AsyncFileSystemNode,
    AsyncFileSystemAdapter,
    AsyncFilteredFileSystemAdapter,
)
from .config import (
    TraversalConfig,
    TraversalStrategy,
    DataRequirement,
)


class AsyncExecutionPlan:
    """Orchestrates async tree traversal with configuration validation.
    
    This class brings together traversers, adapters, and collectors
    to execute a complete tree traversal operation.
    """
    
    def __init__(
        self,
        config: Optional[TraversalConfig] = None,
        adapter: Optional[AsyncTreeAdapter] = None,
        traverser: Optional[AsyncTreeTraverser] = None,
        collector: Optional[AsyncDataCollector] = None
    ):
        """Initialize execution plan.
        
        Args:
            config: Traversal configuration
            adapter: Tree adapter (auto-created if None)
            traverser: Tree traverser (auto-selected if None)
            collector: Data collector (auto-selected if None)
        """
        self.config = config or TraversalConfig()
        
        # Validate configuration
        errors = self.config.validate()
        if errors:
            raise ValueError(f"Invalid configuration: {', '.join(errors)}")
        
        # Set up adapter
        if adapter:
            self.adapter = adapter
        else:
            self.adapter = self._create_adapter()
        
        # Set up traverser
        if traverser:
            self.traverser = traverser
        else:
            self.traverser = self._create_traverser()
        
        # Set up collector
        if collector:
            self.collector = collector
        else:
            self.collector = self._create_collector()
        
        # Track execution statistics
        self.stats = {
            'nodes_visited': 0,
            'nodes_collected': 0,
            'errors': 0,
        }
    
    def _create_adapter(self) -> AsyncTreeAdapter:
        """Create adapter based on configuration."""
        # For now, always create filesystem adapter
        # Future: Support other adapter types
        
        max_concurrent = 100
        if self.config.performance.num_workers:
            max_concurrent = self.config.performance.num_workers
        
        # Check if we need filtering
        if (self.config.filter.include_patterns or 
            self.config.filter.exclude_patterns or
            self.config.filter.include_filter or
            self.config.filter.exclude_filter):
            
            return AsyncFilteredFileSystemAdapter(
                max_concurrent=max_concurrent,
                batch_size=self.config.performance.batch_size or 256,
                include_patterns=list(self.config.filter.include_patterns or []),
                exclude_patterns=list(self.config.filter.exclude_patterns or []),
            )
        
        return AsyncFileSystemAdapter(
            max_concurrent=max_concurrent,
            batch_size=self.config.performance.batch_size or 256,
        )
    
    def _create_traverser(self) -> AsyncTreeTraverser:
        """Create traverser based on strategy."""
        if self.config.strategy == TraversalStrategy.BREADTH_FIRST:
            return AsyncBreadthFirstTraverser(self.config.depth)
        elif self.config.strategy == TraversalStrategy.DEPTH_FIRST_PRE:
            return AsyncDepthFirstTraverser(self.config.depth, pre_order=True)
        elif self.config.strategy == TraversalStrategy.DEPTH_FIRST_POST:
            return AsyncDepthFirstTraverser(self.config.depth, pre_order=False)
        elif self.config.strategy == TraversalStrategy.CUSTOM:
            if not self.config.custom_traverser:
                raise ValueError("Custom traverser required for CUSTOM strategy")
            return self.config.custom_traverser
        else:
            # Default to BFS
            return AsyncBreadthFirstTraverser(self.config.depth)
    
    def _create_collector(self) -> AsyncDataCollector:
        """Create collector based on data requirements."""
        if self.config.data_requirements == DataRequirement.METADATA:
            return AsyncMetadataCollector()
        elif self.config.data_requirements == DataRequirement.CUSTOM:
            if not self.config.custom_collector:
                raise ValueError("Custom collector required for CUSTOM data requirement")
            return self.config.custom_collector
        else:
            # Default to metadata collector
            return AsyncMetadataCollector()
    
    async def execute(
        self,
        root: Any,
        max_depth: Optional[int] = None
    ) -> AsyncIterator[Tuple[Any, Any]]:
        """Execute the traversal plan.
        
        Args:
            root: Root node or path
            max_depth: Override max depth from config
            
        Yields:
            Tuples of (node, collected_data)
        """
        # Convert path to node if needed
        if isinstance(root, (str, Path)):
            root = AsyncFileSystemNode(Path(root))
        
        # Override max depth if specified
        if max_depth is not None:
            self.config.depth.max_depth = max_depth
        
        # Reset statistics
        self.stats = {
            'nodes_visited': 0,
            'nodes_collected': 0,
            'errors': 0,
        }
        
        # Execute traversal
        try:
            async for node in self.traverser.traverse(
                root,
                self.adapter,
                self.config.depth.max_depth
            ):
                self.stats['nodes_visited'] += 1
                
                # Check node limit
                if self.config.performance.max_nodes:
                    if self.stats['nodes_visited'] > self.config.performance.max_nodes:
                        break
                
                # Apply node filter if configured
                if self.config.filter.include_filter:
                    if not self.config.filter.should_include(node):
                        continue
                
                # Collect data
                try:
                    # Calculate depth for collector
                    depth = await self.adapter.get_depth(node)
                    data = await self.collector.collect(node, depth)
                    
                    self.stats['nodes_collected'] += 1
                    
                    # Report progress if callback configured
                    if self.config.progress_callback:
                        if self.stats['nodes_collected'] % self.config.progress_interval == 0:
                            self.config.progress_callback(
                                self.stats['nodes_collected'],
                                self.config.performance.max_nodes
                            )
                    
                    yield node, data
                    
                except Exception as e:
                    self.stats['errors'] += 1
                    
                    # Handle error based on configuration
                    if self.config.on_error:
                        self.config.on_error(node, e)
                    
                    if not self.config.skip_errors:
                        raise
        
        finally:
            # Clean up adapter
            await self.adapter.close()
    
    async def execute_to_list(
        self,
        root: Any,
        max_depth: Optional[int] = None
    ) -> List[Tuple[Any, Any]]:
        """Execute plan and collect all results.
        
        Args:
            root: Root node or path
            max_depth: Override max depth
            
        Returns:
            List of (node, data) tuples
        """
        results = []
        async for node, data in self.execute(root, max_depth):
            results.append((node, data))
        return results
    
    def get_stats(self) -> dict:
        """Get execution statistics.
        
        Returns:
            Dictionary of statistics
        """
        return self.stats.copy()
    
    async def validate_adapter_capabilities(self) -> List[str]:
        """Validate adapter supports required capabilities.
        
        Returns:
            List of missing capabilities (empty if all supported)
        """
        missing = []
        
        # Check required capabilities based on config
        required = set()
        
        if self.config.depth.max_depth is not None:
            required.add('get_depth')
        
        if self.config.filter.include_filter or self.config.filter.exclude_filter:
            required.add('filtering')
        
        if self.config.performance.parallel:
            required.add('streaming')
        
        # Check adapter
        for capability in required:
            if not self.adapter.supports_capability(capability):
                missing.append(capability)
        
        return missing