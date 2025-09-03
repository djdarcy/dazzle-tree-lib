"""
Error handling policies for DazzleTreeLib.

This module provides a flexible error handling system through the Policy pattern,
allowing users to define how errors should be handled during tree traversal.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional
import sys
from pathlib import Path


class ErrorPolicy(ABC):
    """
    Base class for error handling policies.
    
    Subclasses implement different strategies for handling errors
    that occur during filesystem operations.
    """
    
    @abstractmethod
    async def handle(self, error: Exception, method_name: str, node: Any, *args, **kwargs) -> Any:
        """
        Handle an error that occurred during a filesystem operation.
        
        Args:
            error: The exception that was raised
            method_name: Name of the method that failed (e.g., 'list_children')
            node: The filesystem node being processed when the error occurred
            *args: Additional positional arguments from the failed method
            **kwargs: Additional keyword arguments from the failed method
            
        Returns:
            A sensible default value that allows traversal to continue,
            or re-raises the exception to stop traversal.
        """
        pass


class FailFastPolicy(ErrorPolicy):
    """
    Policy that immediately re-raises any error, stopping traversal.
    
    This is the default behavior - any error will halt the entire operation.
    Useful when data integrity is critical and partial results are not acceptable.
    """
    
    async def handle(self, error: Exception, method_name: str, node: Any, *args, **kwargs) -> Any:
        """Re-raise the error immediately."""
        raise error


class ContinueOnErrorsPolicy(ErrorPolicy):
    """
    Policy that logs errors and continues traversal.
    
    Errors are collected for later inspection, and sensible defaults
    are returned to allow traversal to continue. This is useful when
    you want to process as much as possible despite some failures.
    """
    
    def __init__(self, verbose: bool = True):
        """
        Initialize the policy.
        
        Args:
            verbose: If True, print warnings to stderr when errors occur
        """
        self.errors = []
        self.skipped_paths = []
        self.verbose = verbose
    
    async def handle(self, error: Exception, method_name: str, node: Any, *args, **kwargs) -> Any:
        """
        Log the error and return a sensible default.
        
        Returns:
            - Empty list for list_children
            - None for most other methods
        """
        # Extract path if possible
        path = None
        if hasattr(node, 'path'):
            path = node.path
        elif hasattr(node, '__str__'):
            path = str(node)
        
        # Record the error
        error_record = {
            'path': path,
            'method': method_name,
            'error': error,
            'error_type': type(error).__name__,
            'error_message': str(error)
        }
        self.errors.append(error_record)
        
        # Track skipped paths for permission errors
        if isinstance(error, (PermissionError, OSError)):
            if path:
                self.skipped_paths.append(path)
        
        # Log if verbose
        if self.verbose:
            error_msg = str(error)
            if "Access is denied" in error_msg or "WinError 5" in error_msg or isinstance(error, PermissionError):
                print(f"\nWARNING: Skipping inaccessible path '{path}': {error}", file=sys.stderr)
            else:
                print(f"\nWARNING: Error in {method_name} for '{path}': {error}", file=sys.stderr)
        
        # Return sensible defaults based on method
        if method_name in ('get_children', 'list_children'):
            return []  # Empty list allows traversal to continue
        elif method_name == 'calculate_timestamp':
            return None  # No timestamp available
        elif method_name == 'get_metadata':
            return {}  # Empty metadata
        else:
            # For unknown methods, return None as a safe default
            return None
    
    def get_statistics(self) -> dict:
        """
        Get statistics about errors encountered.
        
        Returns:
            Dictionary with error counts and details
        """
        return {
            'total_errors': len(self.errors),
            'permission_errors': sum(1 for e in self.errors if e['error_type'] == 'PermissionError'),
            'os_errors': sum(1 for e in self.errors if e['error_type'] == 'OSError'),
            'skipped_paths': len(self.skipped_paths),
            'errors': self.errors  # Full error details
        }


class RetryPolicy(ErrorPolicy):
    """
    Policy that retries failed operations with exponential backoff.
    
    Useful for network operations or temporary resource conflicts.
    """
    
    def __init__(self, max_retries: int = 3, backoff_factor: float = 2.0):
        """
        Initialize retry policy.
        
        Args:
            max_retries: Maximum number of retry attempts
            backoff_factor: Multiplier for exponential backoff
        """
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.retry_counts = {}
    
    async def handle(self, error: Exception, method_name: str, node: Any, *args, **kwargs) -> Any:
        """
        Retry with exponential backoff or return default after max retries.
        
        Note: This is a simplified implementation. Full retry logic would
        need to actually re-invoke the failed method, which requires
        more integration with the adapter.
        """
        import asyncio
        
        # Track retry attempts
        path = getattr(node, 'path', None)
        if path:
            self.retry_counts[path] = self.retry_counts.get(path, 0) + 1
        
        # For this simplified version, we'll just return defaults
        # A full implementation would need adapter cooperation to retry
        if method_name in ('get_children', 'list_children'):
            return []
        return None


class CollectErrorsPolicy(ErrorPolicy):
    """
    Policy that collects all errors without logging, for batch processing.
    
    Similar to ContinueOnErrorsPolicy but without verbose output.
    Useful for collecting all errors and presenting them at the end.
    """
    
    def __init__(self):
        """Initialize the policy."""
        self.errors = []
        self.skipped_paths = []
    
    async def handle(self, error: Exception, method_name: str, node: Any, *args, **kwargs) -> Any:
        """Silently collect the error and return a default."""
        # Extract path if possible
        path = None
        if hasattr(node, 'path'):
            path = node.path
        
        # Record the error
        self.errors.append({
            'path': path,
            'method': method_name,
            'error': error,
            'error_type': type(error).__name__,
            'error_message': str(error)
        })
        
        if isinstance(error, PermissionError) and path:
            self.skipped_paths.append(path)
        
        # Return sensible defaults
        if method_name in ('get_children', 'list_children'):
            return []
        return None


class ThresholdPolicy(ErrorPolicy):
    """
    Policy that tolerates errors up to a threshold, then fails fast.
    
    Useful when some errors are expected but too many indicate
    a systemic problem that should halt processing.
    """
    
    def __init__(self, max_errors: int = 10, verbose: bool = True):
        """
        Initialize threshold policy.
        
        Args:
            max_errors: Maximum errors to tolerate before failing
            verbose: If True, print warnings for errors
        """
        self.max_errors = max_errors
        self.error_count = 0
        self.verbose = verbose
        self.errors = []
    
    async def handle(self, error: Exception, method_name: str, node: Any, *args, **kwargs) -> Any:
        """Handle error if under threshold, otherwise re-raise."""
        self.error_count += 1
        self.errors.append(error)
        
        if self.error_count > self.max_errors:
            raise RuntimeError(f"Error threshold exceeded ({self.max_errors} errors)") from error
        
        if self.verbose:
            path = getattr(node, 'path', node) if node else 'unknown'
            print(f"\nWARNING [{self.error_count}/{self.max_errors}]: Error in {method_name} for '{path}': {error}", 
                  file=sys.stderr)
        
        # Return defaults to continue
        if method_name in ('get_children', 'list_children'):
            return []
        return None