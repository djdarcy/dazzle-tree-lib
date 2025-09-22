#!/usr/bin/env python
"""
Test for Issue #16: Silent Error Swallowing Fix
================================================

This test verifies that filesystem errors (OSError, PermissionError) are properly
propagated from AsyncFileSystemAdapter to ErrorHandlingAdapter, rather than being
silently swallowed.

Issue #16: The AsyncFileSystemAdapter was silently catching and ignoring OSError
and PermissionError exceptions in get_children(), preventing the ErrorHandlingAdapter
from applying error policies.
"""

import asyncio
import tempfile
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import shutil

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dazzletreelib.aio import (
    AsyncFileSystemAdapter,
    AsyncFileSystemNode,
    ErrorHandlingAdapter,
    ContinueOnErrorsPolicy,
    FailFastPolicy,
    CollectErrorsPolicy
)


class TestIssue16ErrorPropagation(unittest.TestCase):
    """Test that filesystem errors properly propagate to error handling layer."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp(prefix='issue16_test_')
        
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_permission_error_propagates_to_error_handler(self):
        """Test that PermissionError propagates from base adapter to error handler."""
        async def run_test():
            # Create a mock that raises PermissionError when scanning
            base_adapter = AsyncFileSystemAdapter()
            
            # Mock os.scandir to raise PermissionError
            with patch('os.scandir') as mock_scandir:
                mock_scandir.side_effect = PermissionError("Access denied")
                
                # Create error handling adapter with ContinueOnErrors policy
                policy = ContinueOnErrorsPolicy(verbose=False)
                adapter = ErrorHandlingAdapter(base_adapter, policy)
                
                # Create a test node
                test_node = AsyncFileSystemNode(Path(self.test_dir))
                
                # Try to get children - should not crash
                children = []
                error_occurred = False
                
                try:
                    async for child in adapter.get_children(test_node):
                        children.append(child)
                except PermissionError:
                    # With the fix, PermissionError should be caught by ErrorHandlingAdapter
                    # and handled according to policy (ContinueOnErrors should not raise)
                    error_occurred = True
                
                # With ContinueOnErrors, we should not get an exception
                self.assertFalse(error_occurred, "ContinueOnErrors policy should handle PermissionError")
                
                # The policy should have recorded the error
                self.assertGreater(len(policy.errors), 0, "Policy should have recorded the error")
                
                # Check that the error is the expected type
                if policy.errors:
                    first_error = policy.errors[0]
                    self.assertEqual(first_error['error_type'], 'PermissionError')
                    self.assertIn("Access denied", str(first_error.get('error', '')))
        
        # Run the async test
        asyncio.run(run_test())
    
    def test_oserror_propagates_to_error_handler(self):
        """Test that OSError propagates from base adapter to error handler."""
        async def run_test():
            # Create a mock that raises OSError when scanning
            base_adapter = AsyncFileSystemAdapter()
            
            # Mock os.scandir to raise OSError
            with patch('os.scandir') as mock_scandir:
                mock_scandir.side_effect = OSError("I/O error")
                
                # Create error handling adapter with CollectErrors policy
                policy = CollectErrorsPolicy()
                adapter = ErrorHandlingAdapter(base_adapter, policy)
                
                # Create a test node
                test_node = AsyncFileSystemNode(Path(self.test_dir))
                
                # Try to get children
                children = []
                warnings_recorded = False
                
                async for child in adapter.get_children(test_node):
                    children.append(child)
                
                # Check if warnings were recorded
                if hasattr(policy, 'warnings') and policy.warnings:
                    warnings_recorded = True
                elif hasattr(policy, 'errors') and policy.errors:
                    warnings_recorded = True
                
                # The policy should have recorded the warning/error
                self.assertTrue(warnings_recorded or len(policy.errors) > 0, 
                              "Policy should have recorded the error")
        
        # Run the async test
        asyncio.run(run_test())
    
    def test_fail_fast_policy_with_permission_error(self):
        """Test that FailFastPolicy correctly propagates PermissionError."""
        async def run_test():
            # Create a mock that raises PermissionError when scanning
            base_adapter = AsyncFileSystemAdapter()
            
            # Mock os.scandir to raise PermissionError
            with patch('os.scandir') as mock_scandir:
                mock_scandir.side_effect = PermissionError("Access denied")
                
                # Create error handling adapter with FailFast policy
                policy = FailFastPolicy()
                adapter = ErrorHandlingAdapter(base_adapter, policy)
                
                # Create a test node
                test_node = AsyncFileSystemNode(Path(self.test_dir))
                
                # Try to get children - should raise immediately
                error_raised = False
                error_type = None
                
                try:
                    async for child in adapter.get_children(test_node):
                        pass  # Should not reach here
                except PermissionError as e:
                    error_raised = True
                    error_type = type(e).__name__
                except Exception as e:
                    error_raised = True
                    error_type = type(e).__name__
                
                # FailFast should propagate the error
                self.assertTrue(error_raised, "FailFast policy should raise the error")
                self.assertEqual(error_type, "PermissionError", 
                               f"Expected PermissionError, got {error_type}")
        
        # Run the async test
        asyncio.run(run_test())
    
    def test_no_silent_swallowing_in_base_adapter(self):
        """Test that base adapter no longer silently swallows errors."""
        async def run_test():
            # Create base adapter without error handling
            adapter = AsyncFileSystemAdapter()
            
            # Mock os.scandir to raise PermissionError
            with patch('os.scandir') as mock_scandir:
                mock_scandir.side_effect = PermissionError("Access denied")
                
                # Create a test node
                test_node = AsyncFileSystemNode(Path(self.test_dir))
                
                # Try to get children - should raise without error handler
                error_raised = False
                error_message = ""
                
                try:
                    async for child in adapter.get_children(test_node):
                        pass  # Should not reach here
                except PermissionError as e:
                    error_raised = True
                    error_message = str(e)
                
                # Without error handler, the error should propagate
                self.assertTrue(error_raised, 
                              "Base adapter should propagate errors, not swallow them")
                self.assertIn("Access denied", error_message)
        
        # Run the async test
        asyncio.run(run_test())
    
    def test_real_filesystem_permission_error(self):
        """Test with real filesystem permission error (if possible)."""
        async def run_test():
            # Try to create a directory with no read permission
            restricted_dir = Path(self.test_dir) / "restricted"
            restricted_dir.mkdir()
            
            # Add a file inside so it's not empty
            (restricted_dir / "secret.txt").write_text("secret content")
            
            # Try to remove read permission (Windows-specific)
            if sys.platform == "win32":
                # On Windows, we can't easily remove read permissions
                # So we'll skip this test on Windows
                self.skipTest("Cannot reliably create permission errors on Windows")
                return
            else:
                # On Unix-like systems, remove read permission
                os.chmod(restricted_dir, 0o000)
            
            try:
                # Create adapters
                base_adapter = AsyncFileSystemAdapter()
                policy = ContinueOnErrorsPolicy(verbose=False)
                adapter = ErrorHandlingAdapter(base_adapter, policy)
                
                # Try to traverse the restricted directory
                test_node = AsyncFileSystemNode(restricted_dir)
                children = []
                
                async for child in adapter.get_children(test_node):
                    children.append(child)
                
                # Should handle the error gracefully with ContinueOnErrors
                self.assertEqual(len(children), 0, "Should get no children from restricted dir")
                
                # Should have recorded the permission error
                self.assertGreater(len(policy.errors), 0, "Should have recorded permission error")
                
            finally:
                # Restore permissions for cleanup
                if sys.platform != "win32":
                    os.chmod(restricted_dir, 0o755)
        
        # Run the async test
        asyncio.run(run_test())
    
    def test_mixed_accessible_and_inaccessible_directories(self):
        """Test traversal with mix of accessible and inaccessible directories."""
        async def run_test():
            # Create a directory structure
            accessible_dir = Path(self.test_dir) / "accessible"
            accessible_dir.mkdir()
            (accessible_dir / "file1.txt").write_text("content1")
            
            another_dir = Path(self.test_dir) / "another"
            another_dir.mkdir()
            (another_dir / "file2.txt").write_text("content2")
            
            # Mock scandir to fail only for specific directories
            original_scandir = os.scandir
            
            def mock_scandir(path):
                if "accessible" in str(path):
                    raise PermissionError(f"Cannot access {path}")
                return original_scandir(path)
            
            with patch('os.scandir', side_effect=mock_scandir):
                # Create adapters with ContinueOnErrors
                base_adapter = AsyncFileSystemAdapter()
                policy = ContinueOnErrorsPolicy(verbose=False)
                adapter = ErrorHandlingAdapter(base_adapter, policy)
                
                # Traverse the test directory
                test_node = AsyncFileSystemNode(Path(self.test_dir))
                found_nodes = []
                
                async for child in adapter.get_children(test_node):
                    found_nodes.append(child.path.name)
                    
                    # Try to get grandchildren
                    async for grandchild in adapter.get_children(child):
                        found_nodes.append(grandchild.path.name)
                
                # Should find "another" but get error for "accessible"
                self.assertIn("another", found_nodes, "Should find accessible directory")
                
                # Should have recorded error for inaccessible directory
                self.assertGreater(len(policy.errors), 0, "Should record permission errors")
                
                # Check that we found at least one permission error
                permission_errors = [e for e in policy.errors 
                                   if e['error_type'] == 'PermissionError']
                self.assertGreater(len(permission_errors), 0, 
                                 "Should have at least one PermissionError")
        
        # Run the async test
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()