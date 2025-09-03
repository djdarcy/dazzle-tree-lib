"""
Tests for error handling policies and adapter.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from dazzletreelib.aio import (
    AsyncFileSystemAdapter,
    AsyncFileSystemNode,
    ErrorHandlingAdapter,
    ErrorPolicy,
    FailFastPolicy,
    ContinueOnErrorsPolicy,
    RetryPolicy,
    CollectErrorsPolicy,
    ThresholdPolicy,
)


class TestErrorPolicies:
    """Test individual error policy behaviors."""
    
    @pytest.mark.asyncio
    async def test_fail_fast_policy(self):
        """FailFastPolicy should re-raise any error."""
        policy = FailFastPolicy()
        
        with pytest.raises(PermissionError):
            await policy.handle(
                PermissionError("Access denied"),
                "list_children",
                Mock()
            )
    
    @pytest.mark.asyncio
    async def test_continue_on_errors_policy(self):
        """ContinueOnErrorsPolicy should return empty list and track errors."""
        policy = ContinueOnErrorsPolicy(verbose=False)
        
        # Should return empty list for list_children
        result = await policy.handle(
            PermissionError("Access denied"),
            "list_children",
            Mock(path=Path("/test"))
        )
        assert result == []
        assert len(policy.skipped_paths) == 1
        assert Path("/test") in policy.skipped_paths
    
    @pytest.mark.asyncio
    async def test_retry_policy(self):
        """RetryPolicy should track retry attempts."""
        policy = RetryPolicy(max_retries=2, backoff_factor=2.0)
        
        # Mock the retry mechanism
        node = Mock(path=Path("/test"))
        
        # RetryPolicy returns default values and tracks retries
        result = await policy.handle(
            OSError("Temporary failure"),
            "get_children",
            node
        )
        
        # Should return empty list for get_children
        assert result == []
        
        # Should track the path
        assert Path("/test") in policy.retry_counts
        assert policy.retry_counts[Path("/test")] == 1
    
    @pytest.mark.asyncio
    async def test_collect_errors_policy(self):
        """CollectErrorsPolicy should collect all errors."""
        policy = CollectErrorsPolicy()
        
        # Handle multiple errors
        await policy.handle(
            PermissionError("Access denied"),
            "get_children",
            Mock(path=Path("/test1"))
        )
        
        await policy.handle(
            OSError("File not found"),
            "get_metadata",
            Mock(path=Path("/test2"))
        )
        
        assert len(policy.errors) == 2
        # Check error types were collected
        assert any(e['error_type'] == 'PermissionError' for e in policy.errors)
        assert any(e['error_type'] == 'OSError' for e in policy.errors)
    
    @pytest.mark.asyncio
    async def test_threshold_policy(self):
        """ThresholdPolicy should fail after threshold."""
        policy = ThresholdPolicy(max_errors=2)  # Correct parameter name
        
        # First two errors should be handled
        result1 = await policy.handle(
            PermissionError("Error 1"),
            "get_children",
            Mock(path=Path("/test1"))
        )
        assert result1 == []
        
        result2 = await policy.handle(
            PermissionError("Error 2"),
            "get_children",
            Mock(path=Path("/test2"))
        )
        assert result2 == []
        
        # Third error should exceed threshold
        with pytest.raises(RuntimeError) as exc_info:
            await policy.handle(
                PermissionError("Error 3"),
                "get_children",
                Mock(path=Path("/test3"))
            )
        assert "Error threshold exceeded" in str(exc_info.value)


class TestErrorHandlingAdapter:
    """Test the ErrorHandlingAdapter wrapper."""
    
    @pytest.mark.asyncio
    async def test_successful_operation(self):
        """Successful operations should pass through unchanged."""
        # Create mock base adapter
        base_adapter = AsyncMock()
        base_adapter.get_children = AsyncMock(return_value=["child1", "child2"])
        
        policy = FailFastPolicy()
        adapter = ErrorHandlingAdapter(base_adapter, policy)
        
        node = Mock()
        result = await adapter.get_children(node)
        
        assert result == ["child1", "child2"]
        base_adapter.get_children.assert_called_once_with(node)
    
    @pytest.mark.asyncio
    async def test_error_handling_with_continue_policy(self):
        """Errors should be handled by policy."""
        # Create mock base adapter that raises error
        base_adapter = AsyncMock()
        base_adapter.get_children = AsyncMock(
            side_effect=PermissionError("Access denied")
        )
        
        policy = ContinueOnErrorsPolicy(verbose=False)
        adapter = ErrorHandlingAdapter(base_adapter, policy)
        
        node = Mock(path=Path("/restricted"))
        result = await adapter.get_children(node)
        
        # Should return empty list instead of raising
        assert result == []
        assert Path("/restricted") in policy.skipped_paths
    
    @pytest.mark.asyncio
    async def test_error_handling_with_fail_policy(self):
        """Errors should be re-raised with FailFastPolicy."""
        # Create mock base adapter that raises error
        base_adapter = AsyncMock()
        base_adapter.get_children = AsyncMock(
            side_effect=PermissionError("Access denied")
        )
        
        policy = FailFastPolicy()
        adapter = ErrorHandlingAdapter(base_adapter, policy)
        
        node = Mock(path=Path("/restricted"))
        
        with pytest.raises(PermissionError) as exc_info:
            await adapter.get_children(node)
        
        assert "Access denied" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_non_async_method_passthrough(self):
        """Non-async methods should work correctly."""
        base_adapter = Mock()
        base_adapter.some_sync_method = Mock(return_value="sync_result")
        
        policy = FailFastPolicy()
        adapter = ErrorHandlingAdapter(base_adapter, policy)
        
        result = adapter.some_sync_method("arg")
        assert result == "sync_result"
        base_adapter.some_sync_method.assert_called_once_with("arg")
    
    @pytest.mark.asyncio
    async def test_attribute_access(self):
        """Non-callable attributes should be accessible."""
        base_adapter = Mock()
        base_adapter.some_property = "value"
        
        policy = FailFastPolicy()
        adapter = ErrorHandlingAdapter(base_adapter, policy)
        
        assert adapter.some_property == "value"
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Adapter should work as context manager if base does."""
        base_adapter = AsyncMock()
        base_adapter.__aenter__ = AsyncMock(return_value=base_adapter)
        base_adapter.__aexit__ = AsyncMock(return_value=None)
        
        policy = FailFastPolicy()
        adapter = ErrorHandlingAdapter(base_adapter, policy)
        
        async with adapter as ctx:
            assert ctx == adapter
        
        base_adapter.__aenter__.assert_called_once()
        base_adapter.__aexit__.assert_called_once()


class TestIntegration:
    """Integration tests with real filesystem operations."""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not Path("C:/").exists(), reason="Windows-specific test")
    async def test_real_filesystem_with_continue_policy(self, tmp_path):
        """Test with real filesystem operations."""
        # Create test structure
        test_dir = tmp_path / "test_error_handling"
        test_dir.mkdir()
        (test_dir / "accessible").mkdir()
        (test_dir / "accessible" / "file.txt").write_text("test")
        
        # Create base adapter and wrap with error handling
        base_adapter = AsyncFileSystemAdapter()
        policy = ContinueOnErrorsPolicy(verbose=False)
        adapter = ErrorHandlingAdapter(base_adapter, policy)
        
        # Should handle filesystem operations
        root = AsyncFileSystemNode(test_dir)
        children = []
        async for child in adapter.get_children(root):
            children.append(child)
        
        assert len(children) > 0
        assert any(child.path.name == "accessible" for child in children)
    
    @pytest.mark.asyncio
    async def test_create_resilient_adapter(self):
        """Test the create_resilient_adapter helper."""
        from dazzletreelib.aio import create_resilient_adapter, AsyncFileSystemAdapter
        
        # create_resilient_adapter requires a base adapter
        base = AsyncFileSystemAdapter()
        adapter = create_resilient_adapter(base)
        assert isinstance(adapter, ErrorHandlingAdapter)
        assert isinstance(adapter._policy, ContinueOnErrorsPolicy)