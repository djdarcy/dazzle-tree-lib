"""
Error handling adapter for DazzleTreeLib.

This module provides the ErrorHandlingAdapter that wraps other adapters
and delegates error handling to pluggable policies.
"""

import functools
import asyncio
from typing import Any
from .error_policies import ErrorPolicy, FailFastPolicy


class ErrorHandlingAdapter:
    """
    Adapter that wraps another adapter and handles errors through policies.
    
    This adapter uses the dynamic proxy pattern to automatically wrap
    all methods of the underlying adapter, catching exceptions and
    delegating handling to a configurable error policy.
    
    This design allows for flexible error handling strategies without
    modifying the core adapter implementations.
    """
    
    def __init__(self, base_adapter: Any, policy: ErrorPolicy = None):
        """
        Initialize the error handling adapter.
        
        Args:
            base_adapter: The adapter to wrap (e.g., AsyncFileSystemAdapter)
            policy: Error handling policy (defaults to FailFastPolicy)
        """
        self._base_adapter = base_adapter
        self._policy = policy or FailFastPolicy()
    
    async def __aenter__(self):
        """Enter async context manager."""
        if hasattr(self._base_adapter, '__aenter__'):
            await self._base_adapter.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager."""
        if hasattr(self._base_adapter, '__aexit__'):
            return await self._base_adapter.__aexit__(exc_type, exc_val, exc_tb)
        return None
    
    def __getattr__(self, name: str) -> Any:
        """
        Dynamic proxy that wraps all methods with error handling.
        
        This method is called when an attribute is accessed that doesn't
        exist on this object. We use it to proxy to the base adapter,
        wrapping method calls with error handling.
        
        Args:
            name: The attribute name being accessed
            
        Returns:
            The attribute from the base adapter, wrapped if it's a method
        """
        # Get the attribute from the base adapter
        attr = getattr(self._base_adapter, name)
        
        # If it's not callable, return it as-is (properties, attributes)
        if not callable(attr):
            return attr
        
        # Wrap callable methods with error handling
        @functools.wraps(attr)
        def wrapper(*args, **kwargs):
            """
            Wrapper that handles both sync and async methods.
            
            For async methods, we return a coroutine that handles errors.
            For sync methods, we handle errors directly.
            """
            try:
                # Call the original method
                result = attr(*args, **kwargs)
                
                # If it's a coroutine, wrap it with async error handling
                if asyncio.iscoroutine(result):
                    return self._handle_coroutine(result, name, *args, **kwargs)
                
                # If it's an async generator, wrap it with error handling
                # Check using hasattr since inspect.isasyncgen doesn't work on unstarted generators
                if hasattr(result, '__aiter__'):
                    return self._handle_async_generator(result, name, *args, **kwargs)
                
                # For sync methods, return the result directly
                return result
                
            except Exception as e:
                # Handle synchronous errors
                # Note: Most filesystem operations in DazzleTreeLib are async,
                # so this path is less common
                node = args[0] if args else None
                
                # For sync errors, we need to run the async handler synchronously
                # This is not ideal but maintains compatibility
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(
                        self._policy.handle(e, name, node, *args, **kwargs)
                    )
                finally:
                    loop.close()
        
        return wrapper
    
    async def _handle_coroutine(self, coro, method_name: str, *args, **kwargs) -> Any:
        """
        Handle errors in async methods.
        
        This wraps the coroutine execution with try/except to catch
        and handle errors according to the configured policy.
        
        Args:
            coro: The coroutine to execute
            method_name: Name of the method being called
            *args: Original method arguments
            **kwargs: Original method keyword arguments
            
        Returns:
            The result from the coroutine, or a default from the policy
        """
        try:
            # Execute the coroutine
            return await coro
            
        except Exception as e:
            # Extract the node from args (first argument is usually the node)
            node = args[0] if args else None
            
            # Delegate to the policy
            return await self._policy.handle(e, method_name, node, *args, **kwargs)
    
    def get_policy(self) -> ErrorPolicy:
        """
        Get the current error policy.
        
        Returns:
            The configured ErrorPolicy instance
        """
        return self._policy
    
    def set_policy(self, policy: ErrorPolicy) -> None:
        """
        Change the error policy.
        
        Args:
            policy: The new ErrorPolicy to use
        """
        self._policy = policy
    
    def get_base_adapter(self) -> Any:
        """
        Get the wrapped base adapter.
        
        Returns:
            The underlying adapter being wrapped
        """
        return self._base_adapter
    
    # Special methods that might be needed for proper proxying
    def __repr__(self) -> str:
        """String representation."""
        return f"ErrorHandlingAdapter({self._base_adapter!r}, policy={self._policy.__class__.__name__})"
    
    def __str__(self) -> str:
        """String conversion."""
        return f"ErrorHandlingAdapter wrapping {self._base_adapter}"

    
    async def _handle_async_generator(self, gen, method_name: str, *args, **kwargs):
        """
        Handle errors in async generator methods like get_children.
        
        This wraps the async generator to catch exceptions during iteration.
        
        Args:
            gen: The async generator to wrap
            method_name: Name of the method being called
            *args: Original method arguments
            **kwargs: Original method keyword arguments
            
        Yields:
            Items from the generator or handles errors
        """
        node = args[0] if args else None
        
        try:
            # Try to iterate through the async generator
            async for item in gen:
                yield item
        except Exception as e:
            # Handle the error using the policy
            result = await self._policy.handle(e, method_name, node, *args, **kwargs)
            
            # If the policy returns an iterable (like an empty list), yield its items
            if hasattr(result, '__iter__'):
                for item in result:
                    yield item
            # If the policy returns None or another non-iterable, stop iteration
            # This is appropriate for methods like get_children where we expect items

    
    # Introspection methods for testing and debugging
    def get_adapter_by_type(self, adapter_class):
        """
        Find an adapter of a specific type in the chain.
        
        Args:
            adapter_class: The class type to search for
            
        Returns:
            The first adapter of the specified type, or None if not found
        """
        adapter = self
        while adapter:
            if isinstance(adapter, adapter_class):
                return adapter
            # Check both common attribute names
            if hasattr(adapter, '_base_adapter'):
                adapter = adapter._base_adapter
            elif hasattr(adapter, 'base_adapter'):
                adapter = adapter.base_adapter
            else:
                break
        return None
    
    def get_adapter_chain(self):
        """
        Return a list of adapter class names in the chain.
        
        Returns:
            List of class names from this adapter down through the chain
        """
        chain = []
        adapter = self
        while adapter:
            chain.append(adapter.__class__.__name__)
            # Check both common attribute names
            if hasattr(adapter, '_base_adapter'):
                adapter = adapter._base_adapter
            elif hasattr(adapter, 'base_adapter'):
                adapter = adapter.base_adapter
            else:
                break
        return chain
    
    def get_error_policy(self):
        """
        Get the error policy used by this adapter.
        
        Returns:
            The error policy instance
        """
        return self._policy
    
    def has_error_handling(self):
        """
        Check if this adapter has error handling configured.
        
        Returns:
            True (this is an ErrorHandlingAdapter)
        """
        return True


def create_resilient_adapter(base_adapter: Any, strict: bool = False, verbose: bool = True) -> ErrorHandlingAdapter:
    """
    Convenience function to create an error-handling adapter.
    
    Args:
        base_adapter: The adapter to wrap
        strict: If True, use FailFastPolicy; if False, use ContinueOnErrorsPolicy
        verbose: If True, print warnings for errors (only applies when strict=False)
        
    Returns:
        An ErrorHandlingAdapter configured appropriately
    """
    from .error_policies import FailFastPolicy, ContinueOnErrorsPolicy
    
    if strict:
        policy = FailFastPolicy()
    else:
        policy = ContinueOnErrorsPolicy(verbose=verbose)
    
    return ErrorHandlingAdapter(base_adapter, policy)