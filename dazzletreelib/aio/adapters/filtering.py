"""
Filtering adapter for tree traversal.

This adapter wraps another adapter and filters nodes based on criteria.
It provides semantic tracking of what was filtered vs exposed.
"""

from typing import AsyncIterator, Optional, Callable, Any, Union
from pathlib import Path

from ..core import AsyncTreeAdapter


class FilteringWrapper(AsyncTreeAdapter):
    """
    Adapter that filters nodes during traversal.

    This wrapper applies filtering logic and tracks what was filtered,
    providing clear semantics for discovered vs exposed vs filtered nodes.

    Attributes:
        base_adapter: The wrapped adapter providing nodes
        node_filter: Optional callable that returns True to keep nodes
        track_filtered: Whether to track filtered nodes (memory vs correctness tradeoff)
        filtered_paths: Set of paths that were filtered out
    """

    def __init__(
        self,
        base_adapter: AsyncTreeAdapter,
        node_filter: Optional[Callable[[Any], bool]] = None,
        track_filtered: bool = True
    ):
        """
        Initialize the filtering wrapper.

        Args:
            base_adapter: The adapter to wrap
            node_filter: Optional callable(node) -> bool to filter nodes
                        Returns True to keep the node, False to filter it out
            track_filtered: Whether to track filtered nodes for semantic queries
                          Set to False for memory efficiency with heavily filtered trees
        """
        super().__init__()
        self.base_adapter = base_adapter
        self.node_filter = node_filter
        self.track_filtered = track_filtered
        self.filtered_paths = set() if track_filtered else None

    async def get_children(self, node: Any) -> AsyncIterator[Any]:
        """
        Get filtered children of a node.

        Yields only children that pass the filter criteria.
        Tracks filtered nodes if tracking is enabled.
        """
        async for child in self.base_adapter.get_children(node):
            # Get a consistent path string for tracking
            if hasattr(child, 'path'):
                child_path = str(child.path).replace('\\', '/')
            else:
                child_path = str(child).replace('\\', '/')

            # Apply filter
            if self.node_filter is None or self.node_filter(child):
                # Node passes filter, yield it
                yield child
            elif self.track_filtered:
                # Node filtered out, track it
                self.filtered_paths.add(child_path)

    async def get_depth(self, node: Any) -> int:
        """Get node depth - delegates to base adapter."""
        return await self.base_adapter.get_depth(node)

    async def get_parent(self, node: Any) -> Optional[Any]:
        """Get parent node - delegates to base adapter."""
        return await self.base_adapter.get_parent(node)

    # === Tracking API ===

    def was_discovered(self, path: Union[str, Path]) -> bool:
        """
        Check if a node was discovered by the underlying adapter.

        Args:
            path: Path to check

        Returns:
            True if the underlying adapter discovered this node
        """
        if hasattr(self.base_adapter, 'was_discovered'):
            return self.base_adapter.was_discovered(path)
        return False

    def was_expanded(self, path: Union[str, Path]) -> bool:
        """
        Check if a node's children were requested from the underlying adapter.

        Args:
            path: Path to check

        Returns:
            True if the underlying adapter expanded this node
        """
        if hasattr(self.base_adapter, 'was_expanded'):
            return self.base_adapter.was_expanded(path)
        return False

    def was_filtered(self, path: Union[str, Path]) -> bool:
        """
        Check if a node was discovered but then filtered out.

        Args:
            path: Path to check

        Returns:
            True if node was discovered but filtered out
            False if not filtered or tracking is disabled
        """
        if not self.track_filtered:
            # Tracking disabled, cannot determine
            return False

        path_str = str(path).replace('\\', '/')
        # A node is filtered if we tracked it as filtered AND it was discovered
        return path_str in self.filtered_paths and self.was_discovered(path_str)

    def was_exposed(self, path: Union[str, Path]) -> bool:
        """
        Check if a node was discovered and not filtered out (yielded upward).

        This is the key semantic distinction - a node is "exposed" if it
        made it through the filter to be yielded to the layer above.

        Args:
            path: Path to check

        Returns:
            True if node was discovered and not filtered
            False if filtered out or not discovered
        """
        path_str = str(path).replace('\\', '/')

        # First check if it was discovered at all
        if not self.was_discovered(path_str):
            return False

        # If tracking is disabled, assume exposed if discovered
        if not self.track_filtered:
            return True

        # Node is exposed if NOT in our filtered set
        return path_str not in self.filtered_paths

    def clear_tracking(self):
        """Clear all tracking data."""
        if self.filtered_paths is not None:
            self.filtered_paths.clear()
        # Delegate to base adapter if it has the method
        if hasattr(self.base_adapter, 'clear_tracking'):
            self.base_adapter.clear_tracking()

    def get_filtered_count(self) -> int:
        """
        Get count of filtered nodes.

        Returns:
            Number of nodes filtered, or 0 if tracking disabled
        """
        if self.filtered_paths is None:
            return 0
        return len(self.filtered_paths)