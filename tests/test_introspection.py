"""
Test adapter introspection functionality.

This module tests the new introspection methods added to ErrorHandlingAdapter
for better testability and debugging capabilities.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from dazzletreelib.aio import (
    AsyncFileSystemAdapter,
    ErrorHandlingAdapter,
    ContinueOnErrorsPolicy,
    FailFastPolicy,
)


class TestErrorHandlingIntrospection:
    """Test introspection methods on ErrorHandlingAdapter."""
    
    def test_get_error_policy(self):
        """Test that we can retrieve the error policy."""
        base = AsyncFileSystemAdapter()
        policy = ContinueOnErrorsPolicy(verbose=True)
        adapter = ErrorHandlingAdapter(base, policy)
        
        retrieved_policy = adapter.get_error_policy()
        assert retrieved_policy is policy
        assert isinstance(retrieved_policy, ContinueOnErrorsPolicy)
        assert retrieved_policy.verbose == True
    
    def test_has_error_handling(self):
        """Test that has_error_handling returns True."""
        base = AsyncFileSystemAdapter()
        adapter = ErrorHandlingAdapter(base, FailFastPolicy())
        
        assert adapter.has_error_handling() == True
    
    def test_get_adapter_chain_simple(self):
        """Test getting adapter chain with single wrapper."""
        base = AsyncFileSystemAdapter()
        adapter = ErrorHandlingAdapter(base, ContinueOnErrorsPolicy())
        
        chain = adapter.get_adapter_chain()
        assert len(chain) == 2
        assert chain[0] == 'ErrorHandlingAdapter'
        assert chain[1] == 'AsyncFileSystemAdapter'
    
    def test_get_adapter_chain_nested(self):
        """Test getting adapter chain with multiple wrappers."""
        # Create a mock adapter that has _base_adapter
        class MockIntermediateAdapter:
            def __init__(self, base):
                self._base_adapter = base
        
        base = AsyncFileSystemAdapter()
        intermediate = MockIntermediateAdapter(base)
        adapter = ErrorHandlingAdapter(intermediate, ContinueOnErrorsPolicy())
        
        chain = adapter.get_adapter_chain()
        assert len(chain) == 3
        assert chain[0] == 'ErrorHandlingAdapter'
        assert chain[1] == 'MockIntermediateAdapter'
        assert chain[2] == 'AsyncFileSystemAdapter'
    
    def test_get_adapter_by_type_found(self):
        """Test finding an adapter by type when it exists."""
        base = AsyncFileSystemAdapter()
        adapter = ErrorHandlingAdapter(base, ContinueOnErrorsPolicy())
        
        # Find the ErrorHandlingAdapter itself
        found = adapter.get_adapter_by_type(ErrorHandlingAdapter)
        assert found is adapter
        
        # Find the base adapter
        found = adapter.get_adapter_by_type(AsyncFileSystemAdapter)
        assert found is base
    
    def test_get_adapter_by_type_not_found(self):
        """Test finding an adapter by type when it doesn't exist."""
        base = AsyncFileSystemAdapter()
        adapter = ErrorHandlingAdapter(base, ContinueOnErrorsPolicy())
        
        # Look for a non-existent adapter type
        class NonExistentAdapter:
            pass
        
        found = adapter.get_adapter_by_type(NonExistentAdapter)
        assert found is None
    
    def test_get_adapter_by_type_nested(self):
        """Test finding an adapter in a nested chain."""
        # Create a chain of adapters
        class FirstAdapter:
            def __init__(self, base):
                self._base_adapter = base
        
        class SecondAdapter:
            def __init__(self, base):
                self.base_adapter = base  # Note: different attribute name
        
        base = AsyncFileSystemAdapter()
        first = FirstAdapter(base)
        second = SecondAdapter(first)
        adapter = ErrorHandlingAdapter(second, ContinueOnErrorsPolicy())
        
        # Should find all adapters in the chain
        found = adapter.get_adapter_by_type(ErrorHandlingAdapter)
        assert found is adapter
        
        found = adapter.get_adapter_by_type(SecondAdapter)
        assert found is second
        
        found = adapter.get_adapter_by_type(FirstAdapter)
        assert found is first
        
        found = adapter.get_adapter_by_type(AsyncFileSystemAdapter)
        assert found is base
    
    def test_introspection_with_different_policies(self):
        """Test that introspection works with different policy types."""
        base = AsyncFileSystemAdapter()
        
        # Test with ContinueOnErrorsPolicy
        adapter1 = ErrorHandlingAdapter(base, ContinueOnErrorsPolicy(verbose=False))
        policy1 = adapter1.get_error_policy()
        assert isinstance(policy1, ContinueOnErrorsPolicy)
        assert policy1.verbose == False
        
        # Test with FailFastPolicy
        adapter2 = ErrorHandlingAdapter(base, FailFastPolicy())
        policy2 = adapter2.get_error_policy()
        assert isinstance(policy2, FailFastPolicy)
    
    def test_introspection_methods_dont_affect_functionality(self):
        """Test that introspection doesn't interfere with normal operations."""
        base = AsyncFileSystemAdapter()
        adapter = ErrorHandlingAdapter(base, ContinueOnErrorsPolicy())
        
        # Call introspection methods
        _ = adapter.get_error_policy()
        _ = adapter.has_error_handling()
        _ = adapter.get_adapter_chain()
        _ = adapter.get_adapter_by_type(AsyncFileSystemAdapter)
        
        # Adapter should still work normally
        # Test that we can still get the base adapter through the existing method
        assert adapter.get_base_adapter() is base
        
        # Test that the policy getter still works
        assert adapter.get_policy() is adapter.get_error_policy()


class TestIntrospectionUseCases:
    """Test real-world use cases for introspection."""
    
    def test_verify_error_handling_in_strategy(self):
        """Test verifying error handling configuration in a strategy-like class."""
        # Simulate a strategy that builds an adapter stack
        class MockStrategy:
            def __init__(self, verbose=False):
                base = AsyncFileSystemAdapter()
                self.adapter = ErrorHandlingAdapter(
                    base, 
                    ContinueOnErrorsPolicy(verbose=verbose)
                )
            
            def has_error_handling(self):
                # Use introspection to check
                return self.adapter.has_error_handling()
            
            def get_error_policy(self):
                # Use introspection to get policy
                return self.adapter.get_error_policy()
        
        # Test with verbose=True
        strategy = MockStrategy(verbose=True)
        assert strategy.has_error_handling()
        
        policy = strategy.get_error_policy()
        assert isinstance(policy, ContinueOnErrorsPolicy)
        assert policy.verbose == True
        
        # Test with verbose=False
        strategy_quiet = MockStrategy(verbose=False)
        policy_quiet = strategy_quiet.get_error_policy()
        assert policy_quiet.verbose == False
    
    def test_debugging_adapter_chain(self):
        """Test using introspection for debugging adapter chains."""
        # Build a complex adapter stack
        class CacheAdapter:
            def __init__(self, base):
                self._base_adapter = base
        
        class LoggingAdapter:
            def __init__(self, base):
                self._base_adapter = base
        
        base = AsyncFileSystemAdapter()
        cache = CacheAdapter(base)
        logging = LoggingAdapter(cache)
        adapter = ErrorHandlingAdapter(logging, ContinueOnErrorsPolicy())
        
        # Get the full chain for debugging
        chain = adapter.get_adapter_chain()
        
        # Verify the expected chain
        assert chain == [
            'ErrorHandlingAdapter',
            'LoggingAdapter',
            'CacheAdapter',
            'AsyncFileSystemAdapter'
        ]
        
        # Find specific adapters
        cache_adapter = adapter.get_adapter_by_type(CacheAdapter)
        assert cache_adapter is not None
        assert isinstance(cache_adapter, CacheAdapter)