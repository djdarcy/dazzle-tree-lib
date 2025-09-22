"""
Test tracking behavior during error conditions.

This module tests how the SmartCachingAdapter maintains tracking
consistency when errors occur during tree traversal.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from pathlib import Path

from dazzletreelib.aio.adapters.smart_caching import SmartCachingAdapter
from dazzletreelib.aio.error_handling import ErrorHandlingAdapter
from dazzletreelib.aio.error_policies import (
    FailFastPolicy,
    ContinueOnErrorsPolicy,
    CollectErrorsPolicy
)


class ErrorNode:
    """Node that can trigger errors on demand."""

    def __init__(self, path, should_error=False, error_on_expand=False):
        self.path = path
        self.should_error = should_error
        self.error_on_expand = error_on_expand

    def __str__(self):
        return str(self.path)


class ErrorProneAdapter:
    """Adapter that can simulate errors during traversal."""

    def __init__(self, tree_structure=None):
        self.tree = tree_structure or {
            '/': ['/a', '/b', '/c'],
            '/a': ['/a/1', '/a/2'],
            '/a/1': 'ERROR',  # Will error when expanded
            '/a/2': ['/a/2/x'],
            '/b': 'PERMISSION_ERROR',  # Permission denied
            '/c': ['/c/1', '/c/2'],
        }
        self.get_children_calls = []
        self.errors_triggered = []

    async def get_children(self, node):
        """Yield children, potentially raising errors."""
        path = str(node.path) if hasattr(node, 'path') else str(node)
        self.get_children_calls.append(path)

        children_or_error = self.tree.get(path, [])

        # Check for error conditions
        if children_or_error == 'ERROR':
            self.errors_triggered.append(path)
            raise RuntimeError(f"Failed to expand node: {path}")
        elif children_or_error == 'PERMISSION_ERROR':
            self.errors_triggered.append(path)
            raise PermissionError(f"Permission denied: {path}")

        # Check if node itself should error during expansion
        if hasattr(node, 'error_on_expand') and node.error_on_expand:
            self.errors_triggered.append(path)
            raise ValueError(f"Node error during expansion: {path}")

        # Yield children normally
        for child_path in children_or_error:
            # Check if child should error on discovery
            if hasattr(node, 'should_error') and node.should_error:
                self.errors_triggered.append(child_path)
                raise RuntimeError(f"Error discovering child: {child_path}")
            yield ErrorNode(child_path)

    async def get_depth(self, node):
        """Return depth based on path."""
        path = str(node.path) if hasattr(node, 'path') else str(node)
        if path == '/':
            return 0
        parts = [p for p in path.split('/') if p]
        return len(parts)

    async def get_parent(self, node):
        """Return mock parent."""
        return None


class TestErrorDuringTraversal:
    """Test tracking consistency when errors occur."""

    @pytest.mark.asyncio
    async def test_discovery_persists_after_expansion_error(self):
        """Test that discovery is tracked even if expansion fails."""
        error_adapter = ErrorProneAdapter()
        caching_adapter = SmartCachingAdapter(
            error_adapter,
            track_traversal=True,
            max_memory_mb=100
        )

        # Use continue on errors policy
        adapter = ErrorHandlingAdapter(
            caching_adapter,
            policy=ContinueOnErrorsPolicy()
        )

        # Traverse the tree, continuing on errors
        discovered_nodes = []
        expansion_errors = []

        async def traverse(node, path='/'):
            discovered_nodes.append(path)
            try:
                async for child in adapter.get_children(node):
                    child_path = str(child.path)
                    await traverse(child, child_path)
            except Exception as e:
                expansion_errors.append((path, str(e)))

        root = ErrorNode('/')
        await traverse(root)

        # Verify tracking state
        assert caching_adapter.was_discovered('/'), "Root should be discovered"
        assert caching_adapter.was_expanded('/'), "Root should be expanded"

        # Node /a should be discovered and expanded
        assert caching_adapter.was_discovered('/a'), "/a should be discovered"
        assert caching_adapter.was_expanded('/a'), "/a should be expanded"

        # Node /a/1 should be discovered but expansion failed
        assert caching_adapter.was_discovered('/a/1'), "/a/1 should be discovered even though expansion failed"
        # Note: /a/1 will still show as expanded because get_children was called
        assert caching_adapter.was_expanded('/a/1'), "/a/1 expansion was attempted"

        # Node /b should be discovered but expansion failed (permission error)
        assert caching_adapter.was_discovered('/b'), "/b should be discovered"
        assert caching_adapter.was_expanded('/b'), "/b expansion was attempted"

        # Node /c should work normally
        assert caching_adapter.was_discovered('/c'), "/c should be discovered"
        assert caching_adapter.was_expanded('/c'), "/c should be expanded"

    @pytest.mark.asyncio
    async def test_tracking_consistency_with_permission_errors(self):
        """Test tracking remains consistent with permission errors."""
        error_adapter = ErrorProneAdapter()
        caching_adapter = SmartCachingAdapter(
            error_adapter,
            track_traversal=True,
            max_memory_mb=100
        )

        root = ErrorNode('/')

        # Traverse and collect results
        discovered = []
        permission_errors = []

        async for child in caching_adapter.get_children(root):
            discovered.append(str(child.path))
            try:
                # Try to expand each child
                async for grandchild in caching_adapter.get_children(child):
                    discovered.append(str(grandchild.path))
            except PermissionError as e:
                permission_errors.append(str(child.path))
            except Exception:
                pass  # Other errors

        # Verify /b had permission error but was still discovered
        assert '/b' in discovered, "/b should be discovered"
        assert caching_adapter.was_discovered('/b'), "/b should be tracked as discovered"
        assert '/b' in permission_errors, "/b should have permission error"

    @pytest.mark.asyncio
    async def test_partial_traversal_tracking_state(self):
        """Test tracking state after partial traversal due to error."""
        error_adapter = ErrorProneAdapter()
        caching_adapter = SmartCachingAdapter(
            error_adapter,
            track_traversal=True,
            max_memory_mb=100
        )

        # Use fail-fast policy
        adapter = ErrorHandlingAdapter(
            caching_adapter,
            policy=FailFastPolicy()
        )

        root = ErrorNode('/')

        # Try to traverse - should handle errors based on policy
        error_occurred = False
        try:
            async for child in adapter.get_children(root):
                if str(child.path) == '/a':
                    # This will trigger error on /a/1
                    try:
                        async for grandchild in adapter.get_children(child):
                            pass
                    except (RuntimeError, StopAsyncIteration):
                        error_occurred = True
                        break
        except (RuntimeError, StopAsyncIteration):
            error_occurred = True

        # Check partial tracking state
        assert caching_adapter.was_discovered('/'), "Root discovered"
        assert caching_adapter.was_expanded('/'), "Root expanded"
        assert caching_adapter.was_discovered('/a'), "/a discovered before error"
        assert caching_adapter.was_expanded('/a'), "/a expanded before error"
        assert caching_adapter.was_discovered('/a/1'), "/a/1 discovered before its error"

    @pytest.mark.asyncio
    async def test_cache_invalidation_during_error(self):
        """Test that cache can be invalidated even after errors."""
        error_adapter = ErrorProneAdapter()
        caching_adapter = SmartCachingAdapter(
            error_adapter,
            track_traversal=True,
            max_memory_mb=100
        )

        root = ErrorNode('/')

        # First traversal with errors
        try:
            async for child in caching_adapter.get_children(root):
                try:
                    async for grandchild in caching_adapter.get_children(child):
                        pass
                except:
                    pass  # Ignore errors
        except:
            pass

        # Cache should have some entries
        stats = caching_adapter.get_stats()
        assert stats['cache_enabled'], "Cache should be enabled"

        # Invalidate cache
        invalidated = await caching_adapter.invalidate('/a', deep=True)
        assert invalidated > 0, "Should invalidate some entries"

        # Tracking should remain
        assert caching_adapter.was_discovered('/a'), "Discovery tracking persists after invalidation"
        assert caching_adapter.was_expanded('/a'), "Expansion tracking persists after invalidation"

    @pytest.mark.asyncio
    async def test_error_policy_interaction_with_tracking(self):
        """Test different error policies maintain tracking correctly."""

        async def test_with_policy(policy_class):
            error_adapter = ErrorProneAdapter()
            caching_adapter = SmartCachingAdapter(
                error_adapter,
                track_traversal=True,
                max_memory_mb=100
            )

            adapter = ErrorHandlingAdapter(
                caching_adapter,
                policy=policy_class()
            )

            root = ErrorNode('/')
            discovered = set()

            try:
                async for child in adapter.get_children(root):
                    discovered.add(str(child.path))
                    try:
                        async for grandchild in adapter.get_children(child):
                            discovered.add(str(grandchild.path))
                    except:
                        pass
            except:
                pass  # FailFastPolicy will raise

            # All policies should track discovered nodes
            for path in discovered:
                assert caching_adapter.was_discovered(path), f"{path} should be tracked with {policy_class.__name__}"

            return len(discovered)

        # Test with different policies
        fail_fast_count = await test_with_policy(FailFastPolicy)
        continue_count = await test_with_policy(ContinueOnErrorsPolicy)
        collect_count = await test_with_policy(CollectErrorsPolicy)

        # Continue and Collect policies should discover more nodes than FailFast
        assert continue_count >= fail_fast_count, "Continue policy should process more nodes"
        assert collect_count >= fail_fast_count, "Collect policy should process more nodes"

    @pytest.mark.asyncio
    async def test_concurrent_error_and_success_paths(self):
        """Test tracking with concurrent traversals where some fail."""
        error_adapter = ErrorProneAdapter()
        caching_adapter = SmartCachingAdapter(
            error_adapter,
            track_traversal=True,
            max_memory_mb=100
        )

        root = ErrorNode('/')

        async def traverse_branch(branch_path):
            """Traverse a specific branch."""
            branch_node = ErrorNode(branch_path)
            results = []
            errors = []

            try:
                async for child in caching_adapter.get_children(branch_node):
                    results.append(str(child.path))
            except Exception as e:
                errors.append(str(e))

            return results, errors

        # Get root children first
        children = []
        async for child in caching_adapter.get_children(root):
            children.append(str(child.path))

        # Concurrently traverse all branches
        tasks = [traverse_branch(child_path) for child_path in children]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all branches were discovered
        for child_path in children:
            assert caching_adapter.was_discovered(child_path), f"{child_path} should be discovered"
            assert caching_adapter.was_expanded(child_path), f"{child_path} should be expanded"

        # Check that successful branches have their children tracked
        assert caching_adapter.was_discovered('/c/1'), "/c/1 should be discovered (success path)"
        assert caching_adapter.was_discovered('/c/2'), "/c/2 should be discovered (success path)"

    @pytest.mark.asyncio
    async def test_tracking_rollback_not_needed(self):
        """Test that tracking doesn't need rollback - it records attempts."""
        error_adapter = ErrorProneAdapter()
        caching_adapter = SmartCachingAdapter(
            error_adapter,
            track_traversal=True,
            max_memory_mb=100
        )

        # Create a node that will error
        error_node = ErrorNode('/a/1', error_on_expand=True)

        # Attempt expansion (will fail)
        with pytest.raises(RuntimeError):
            async for child in caching_adapter.get_children(error_node):
                pass

        # Node should still be marked as expanded (attempt was made)
        assert caching_adapter.was_expanded('/a/1'), "Expansion attempt should be tracked even on failure"

        # This is correct behavior - tracking records what was attempted,
        # not just what succeeded

    @pytest.mark.asyncio
    async def test_memory_cleanup_after_errors(self):
        """Test that memory is properly managed even with errors."""
        error_adapter = ErrorProneAdapter()
        caching_adapter = SmartCachingAdapter(
            error_adapter,
            track_traversal=True,
            max_memory_mb=1  # Small cache to test memory management
        )

        root = ErrorNode('/')

        # Perform many traversals with errors
        for i in range(10):
            try:
                async for child in caching_adapter.get_children(root):
                    try:
                        async for grandchild in caching_adapter.get_children(child):
                            pass
                    except:
                        pass
            except:
                pass

        # Check memory usage is within bounds
        stats = caching_adapter.get_stats()
        if 'memory_mb' in stats:
            assert stats['memory_mb'] <= 1.5, "Memory should stay within bounds despite errors"

        # Tracking should still work
        assert caching_adapter.was_discovered('/'), "Root should be tracked"
        assert caching_adapter.was_expanded('/'), "Root should be expanded"

    @pytest.mark.asyncio
    async def test_error_during_concurrent_traversals(self):
        """Test tracking consistency with errors in concurrent traversals."""
        error_adapter = ErrorProneAdapter()
        caching_adapter = SmartCachingAdapter(
            error_adapter,
            track_traversal=True,
            max_memory_mb=100
        )

        root = ErrorNode('/')

        async def traverse_with_errors():
            """Traverse handling errors."""
            discovered = []
            async for child in caching_adapter.get_children(root):
                discovered.append(str(child.path))
                try:
                    async for grandchild in caching_adapter.get_children(child):
                        discovered.append(str(grandchild.path))
                except:
                    pass  # Ignore errors
            return discovered

        # Run multiple concurrent traversals
        tasks = [traverse_with_errors() for _ in range(3)]
        results = await asyncio.gather(*tasks)

        # All traversals should have discovered the root children
        for result in results:
            assert '/a' in result, "All traversals should discover /a"
            assert '/c' in result, "All traversals should discover /c"

        # Tracking should be consistent
        assert caching_adapter.was_discovered('/a'), "/a should be tracked"
        assert caching_adapter.was_discovered('/c'), "/c should be tracked"

        # Stats should show discovered nodes
        stats = caching_adapter.get_stats()
        assert stats['discovered_nodes'] >= 3, "Should track at least root and direct children"