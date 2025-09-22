"""Filesystem adapter for DazzleTreeLib.

This adapter enables DazzleTreeLib to work with filesystem trees,
including support for UNCtools for network path handling.
"""

import os
import stat
from pathlib import Path
from typing import Iterator, Optional, Dict, Any, Union
from datetime import datetime
from ..core.node import TreeNode
from ..core.adapter import TreeAdapter


class FileSystemNode(TreeNode):
    """Concrete node implementation for filesystem entries.
    
    Represents a file or directory in the filesystem.
    Designed to be lightweight - most data is computed on demand.
    """
    
    def __init__(self, 
                 path: Union[str, Path],
                 parent: Optional['FileSystemNode'] = None,
                 stat_result: Optional[os.stat_result] = None):
        """Initialize a filesystem node.
        
        Args:
            path: Path to the file or directory
            parent: Parent node (None for root)
            stat_result: Cached stat result to avoid repeated syscalls
        """
        self.path = Path(path) if isinstance(path, str) else path
        self._parent = parent
        self._stat_result = stat_result
        self._metadata = None
    
    def identifier(self) -> str:
        """Return absolute path as unique identifier."""
        try:
            return str(self.path.absolute())
        except Exception:
            # Fallback for special paths
            return str(self.path)
    
    def is_leaf(self) -> bool:
        """Check if this is a leaf node (file or empty directory)."""
        try:
            return not self.path.is_dir()
        except Exception:
            # If we can't determine, assume it's a leaf
            return True
    
    def metadata(self) -> Dict[str, Any]:
        """Return filesystem metadata for this node."""
        if self._metadata is None:
            self._metadata = self._compute_metadata()
        return self._metadata
    
    def _compute_metadata(self) -> Dict[str, Any]:
        """Compute metadata from filesystem."""
        metadata = {
            'name': self.path.name or str(self.path),
            'path': str(self.path),
            'exists': self.path.exists(),
        }
        
        try:
            # Get stat info (use cached if available)
            if self._stat_result is None:
                self._stat_result = self.path.stat()
            
            st = self._stat_result
            
            # Basic metadata
            metadata.update({
                'size': st.st_size,
                'mtime': st.st_mtime,
                'mtime_dt': datetime.fromtimestamp(st.st_mtime),
                'ctime': st.st_ctime,
                'ctime_dt': datetime.fromtimestamp(st.st_ctime),
                'atime': st.st_atime,
                'atime_dt': datetime.fromtimestamp(st.st_atime),
                'mode': st.st_mode,
                'uid': getattr(st, 'st_uid', None),
                'gid': getattr(st, 'st_gid', None),
            })
            
            # File type information
            mode = st.st_mode
            metadata.update({
                'is_file': stat.S_ISREG(mode),
                'is_dir': stat.S_ISDIR(mode),
                'is_link': stat.S_ISLNK(mode) if hasattr(stat, 'S_ISLNK') else False,
                'is_mount': self.path.is_mount() if hasattr(self.path, 'is_mount') else False,
            })
            
            # Permissions (Unix-style, may not work on Windows)
            try:
                metadata.update({
                    'readable': os.access(self.path, os.R_OK),
                    'writable': os.access(self.path, os.W_OK),
                    'executable': os.access(self.path, os.X_OK),
                })
            except Exception:
                pass
            
            # Extension for files
            if metadata['is_file']:
                metadata['extension'] = self.path.suffix
            
        except PermissionError:
            metadata['error'] = 'Permission denied'
        except Exception as e:
            metadata['error'] = str(e)
        
        return metadata
    
    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return f"FileSystemNode(path={self.path!r})"


class FileSystemAdapter(TreeAdapter):
    """Adapter for filesystem tree traversal.
    
    Provides filesystem-specific navigation logic with optional
    UNCtools integration for network path support.
    """
    
    def __init__(self,
                 follow_symlinks: bool = False,
                 use_unctools: bool = False,
                 include_hidden: bool = True):
        """Initialize filesystem adapter.
        
        Args:
            follow_symlinks: Whether to follow symbolic links
            use_unctools: Whether to use UNCtools for network paths
            include_hidden: Whether to include hidden files/directories
        """
        self.follow_symlinks = follow_symlinks
        self.include_hidden = include_hidden
        
        # Try to import UNCtools if requested
        self.unctools = None
        if use_unctools:
            try:
                import unctools
                self.unctools = unctools
            except ImportError:
                # UNCtools not available, fall back to standard paths
                pass
    
    def get_children(self, node: FileSystemNode) -> Iterator[FileSystemNode]:
        """Get child nodes (files and subdirectories)."""
        if not node.path.is_dir():
            return  # No children for files
        
        try:
            # Use iterdir for lazy iteration
            for child_path in sorted(node.path.iterdir()):
                # Skip hidden files if configured
                if not self.include_hidden and child_path.name.startswith('.'):
                    continue
                
                # Skip symlinks if not following
                if not self.follow_symlinks and child_path.is_symlink():
                    continue
                
                # Create child node with parent reference
                yield FileSystemNode(child_path, parent=node)
                
        except PermissionError:
            # Can't read directory, no children to yield
            pass
        except Exception:
            # Other errors, no children to yield
            pass
    
    def get_parent(self, node: FileSystemNode) -> Optional[FileSystemNode]:
        """Get parent directory node."""
        # Use cached parent if available
        if node._parent is not None:
            return node._parent
        
        # Compute parent from path
        parent_path = node.path.parent
        
        # Check if we're at root
        if parent_path == node.path:
            return None  # Root has no parent
        
        return FileSystemNode(parent_path)
    
    def get_depth(self, node: FileSystemNode) -> int:
        """Calculate depth more efficiently using path components."""
        # For filesystem, we can count path components
        try:
            # Get relative path from root
            parts = node.path.parts
            
            # Handle different OS root representations
            if os.name == 'nt':  # Windows
                # On Windows, parts[0] is drive letter (e.g., 'C:')
                # Depth 0 is the drive root
                return len(parts) - 1
            else:  # Unix-like
                # On Unix, parts[0] is '/'
                # Depth 0 is root
                return len(parts) - 1 if parts[0] == '/' else len(parts)
                
        except Exception:
            # Fall back to default implementation
            return super().get_depth(node)
    
    def supports_full_data(self) -> bool:
        """Filesystem adapter can provide full metadata."""
        return True
    
    def supports_random_access(self) -> bool:
        """Filesystem supports jumping to any path."""
        return True
    
    def estimated_size(self, node: FileSystemNode) -> Optional[int]:
        """Estimate number of nodes in subtree."""
        # This is expensive for filesystem, return None
        # Could implement sampling-based estimation in future
        return None
    
    def resolve_path(self, path: Union[str, Path]) -> Path:
        """Resolve a path, handling UNC paths if UNCtools available.
        
        Args:
            path: Path to resolve
            
        Returns:
            Resolved Path object
        """
        path = Path(path) if isinstance(path, str) else path
        
        if self.unctools:
            try:
                # Use UNCtools to resolve network paths
                path_info = self.unctools.get_path_info(str(path))
                if path_info and 'resolved_path' in path_info:
                    return Path(path_info['resolved_path'])
            except Exception:
                # Fall back to standard path if UNCtools fails
                pass
        
        # Resolve symlinks if following them
        if self.follow_symlinks:
            try:
                return path.resolve()
            except Exception:
                pass
        
        return path
    
    def create_node(self, path: Union[str, Path]) -> FileSystemNode:
        """Create a node for a given path.
        
        Convenience method for creating nodes with proper path resolution.
        
        Args:
            path: Path to create node for
            
        Returns:
            FileSystemNode instance
        """
        resolved_path = self.resolve_path(path)
        return FileSystemNode(resolved_path)


class FilteredFileSystemAdapter(FileSystemAdapter):
    """Filesystem adapter with built-in filtering.
    
    Useful for excluding certain paths or file types during traversal.
    """
    
    def __init__(self,
                 exclude_dirs: Optional[set] = None,
                 exclude_extensions: Optional[set] = None,
                 **kwargs):
        """Initialize filtered adapter.
        
        Args:
            exclude_dirs: Directory names to exclude (e.g., {'.git', '__pycache__'})
            exclude_extensions: File extensions to exclude (e.g., {'.pyc', '.tmp'})
            **kwargs: Other FileSystemAdapter arguments
        """
        super().__init__(**kwargs)
        self.exclude_dirs = exclude_dirs or set()
        self.exclude_extensions = exclude_extensions or set()
    
    def get_children(self, node: FileSystemNode) -> Iterator[FileSystemNode]:
        """Get children with filtering applied."""
        for child in super().get_children(node):
            # Check directory exclusions
            if child.path.is_dir() and child.path.name in self.exclude_dirs:
                continue
            
            # Check extension exclusions
            if child.path.is_file() and child.path.suffix in self.exclude_extensions:
                continue
            
            yield child