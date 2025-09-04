"""
Test for Issue #15: CRITICAL BUG: new_event_loop() crashes in async contexts

This test verifies that the ErrorHandlingAdapter doesn't create a new event loop
when handling synchronous errors in an async context, which would cause a
RuntimeError.
"""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

from dazzletreelib.aio.error_handling import ErrorHandlingAdapter
from dazzletreelib.aio.error_policies import (
    ContinueOnErrorsPolicy, 
    FailFastPolicy,
    CollectErrorsPolicy
)


class MockAdapter:
    """Mock adapter that can raise sync or async errors."""
    
    def __init__(self, raise_sync_error=False, raise_async_error=False):
        self.raise_sync_error = raise_sync_error
        self.raise_async_error = raise_async_error
    
    def sync_method(self, node):
        """A synchronous method that might raise an error."""
        if self.raise_sync_error:
            raise PermissionError("Sync permission denied")
        return "sync_result"
    
    async def async_method(self, node):
        """An async method that might raise an error."""
        if self.raise_async_error:
            raise PermissionError("Async permission denied")
        return "async_result"
    
    async def get_children(self, node):
        """Async generator method."""
        if self.raise_async_error:
            raise PermissionError("Cannot list children")
        for i in range(3):
            yield f"child_{i}"


@pytest.mark.asyncio
async def test_sync_error_in_async_context_with_continue_policy():
    """
    Test that sync errors in async context don't crash with ContinueOnErrorsPolicy.
    
    This was the main bug: creating a new event loop when already in one.
    """
    # Create adapter that will raise a sync error
    base_adapter = MockAdapter(raise_sync_error=True)
    policy = ContinueOnErrorsPolicy(verbose=False)
    adapter = ErrorHandlingAdapter(base_adapter, policy)
    
    # Call from within an async context (this test is async)
    # This should NOT crash with "RuntimeError: This event loop is already running"
    result = adapter.sync_method(Mock(path=Path("/test")))
    
    # With ContinueOnErrorsPolicy, we should get None for unknown methods
    assert result is None
    
    # The error should be recorded
    assert len(policy.errors) == 1
    assert policy.errors[0]['error_type'] == 'PermissionError'


@pytest.mark.asyncio
async def test_sync_error_in_async_context_with_fail_fast_policy():
    """
    Test that sync errors with FailFastPolicy re-raise the error properly.
    """
    base_adapter = MockAdapter(raise_sync_error=True)
    policy = FailFastPolicy()
    adapter = ErrorHandlingAdapter(base_adapter, policy)
    
    # Should re-raise the error
    with pytest.raises(PermissionError, match="Sync permission denied"):
        adapter.sync_method(Mock(path=Path("/test")))


def test_sync_error_in_sync_context():
    """
    Test that sync errors in sync context still work (no async loop).
    """
    base_adapter = MockAdapter(raise_sync_error=True)
    policy = ContinueOnErrorsPolicy(verbose=False)
    adapter = ErrorHandlingAdapter(base_adapter, policy)
    
    # Call from sync context (no event loop)
    result = adapter.sync_method(Mock(path=Path("/test")))
    
    # Should handle the error and return None
    assert result is None
    assert len(policy.errors) == 1


@pytest.mark.asyncio
async def test_async_error_handling_still_works():
    """
    Test that async error handling wasn't broken by the fix.
    """
    base_adapter = MockAdapter(raise_async_error=True)
    policy = ContinueOnErrorsPolicy(verbose=False)
    adapter = ErrorHandlingAdapter(base_adapter, policy)
    
    # Async errors should still be handled properly
    result = await adapter.async_method(Mock(path=Path("/test")))
    
    # Should handle the error and return None
    assert result is None
    assert len(policy.errors) == 1


@pytest.mark.asyncio
async def test_async_generator_error_handling():
    """
    Test that async generator error handling still works.
    """
    base_adapter = MockAdapter(raise_async_error=True)
    policy = ContinueOnErrorsPolicy(verbose=False)
    adapter = ErrorHandlingAdapter(base_adapter, policy)
    
    # Collect results from async generator
    results = []
    async for item in adapter.get_children(Mock(path=Path("/test"))):
        results.append(item)
    
    # With error, should get empty results
    assert results == []
    assert len(policy.errors) == 1


@pytest.mark.asyncio
async def test_mixed_sync_async_errors():
    """
    Test handling both sync and async errors in the same session.
    """
    base_adapter = MockAdapter()
    policy = CollectErrorsPolicy()
    adapter = ErrorHandlingAdapter(base_adapter, policy)
    
    # First, successful calls
    sync_result = adapter.sync_method(Mock(path=Path("/test1")))
    assert sync_result == "sync_result"
    
    async_result = await adapter.async_method(Mock(path=Path("/test2")))
    assert async_result == "async_result"
    
    # Now with errors
    base_adapter.raise_sync_error = True
    base_adapter.raise_async_error = True
    
    # Both should be handled without crashes
    sync_error_result = adapter.sync_method(Mock(path=Path("/test3")))
    assert sync_error_result is None
    
    async_error_result = await adapter.async_method(Mock(path=Path("/test4")))
    assert async_error_result is None
    
    # Both errors should be collected
    assert len(policy.errors) == 2
    assert policy.errors[0]['path'] == Path("/test3")
    assert policy.errors[1]['path'] == Path("/test4")


@pytest.mark.asyncio
async def test_no_regression_on_normal_operations():
    """
    Test that normal operations (no errors) still work correctly.
    """
    base_adapter = MockAdapter()
    policy = ContinueOnErrorsPolicy(verbose=False)
    adapter = ErrorHandlingAdapter(base_adapter, policy)
    
    # Normal sync call
    assert adapter.sync_method(Mock()) == "sync_result"
    
    # Normal async call
    assert await adapter.async_method(Mock()) == "async_result"
    
    # Normal async generator
    results = []
    async for item in adapter.get_children(Mock()):
        results.append(item)
    assert results == ["child_0", "child_1", "child_2"]
    
    # No errors should be recorded
    assert len(policy.errors) == 0


def test_policy_handle_sync_implementations():
    """
    Test that each policy has a working handle_sync method.
    """
    mock_error = PermissionError("Test error")
    mock_node = Mock(path=Path("/test"))
    
    # FailFastPolicy should re-raise
    policy = FailFastPolicy()
    with pytest.raises(PermissionError):
        policy.handle_sync(mock_error, "test_method", mock_node)
    
    # ContinueOnErrorsPolicy should return defaults
    policy = ContinueOnErrorsPolicy(verbose=False)
    result = policy.handle_sync(mock_error, "get_children", mock_node)
    assert result == []
    
    result = policy.handle_sync(mock_error, "unknown_method", mock_node)
    assert result is None
    
    # CollectErrorsPolicy should collect and return defaults
    policy = CollectErrorsPolicy()
    result = policy.handle_sync(mock_error, "get_children", mock_node)
    assert result == []
    assert len(policy.errors) == 1


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])