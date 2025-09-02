"""
Timestamp calculation adapter for DazzleTreeLib.

This adapter provides smart timestamp calculation strategies for folders,
supporting shallow, deep, and smart modes like folder_datetime_fix needs.
"""

from typing import Optional, Any, Dict
from datetime import datetime
from pathlib import Path
import os
from ..core import AsyncTreeAdapter
from .filesystem import AsyncFileSystemNode


class TimestampCalculationAdapter(AsyncTreeAdapter):
    """
    Adapter that calculates timestamps for folders using different strategies.
    
    This is designed to support folder_datetime_fix's timestamp calculation needs:
    - Shallow: Only immediate children
    - Deep: Full recursive scan
    - Smart: Adaptive based on folder age
    """
    
    def __init__(self, base_adapter: AsyncTreeAdapter, strategy: str = 'shallow'):
        """
        Initialize timestamp adapter.
        
        Args:
            base_adapter: The underlying adapter to wrap
            strategy: 'shallow', 'deep', or 'smart'
        """
        self.base_adapter = base_adapter
        self.strategy = strategy
        self.smart_threshold_days = 7  # For smart strategy
    
    async def get_children(self, node: Any):
        """Pass through to base adapter."""
        async for child in self.base_adapter.get_children(node):
            yield child
    
    async def get_parent(self, node: Any) -> Optional[Any]:
        """Pass through to base adapter."""
        return await self.base_adapter.get_parent(node)
    
    async def get_depth(self, node: Any) -> int:
        """Pass through to base adapter."""
        return await self.base_adapter.get_depth(node)
    
    def is_leaf(self, node: Any) -> bool:
        """Pass through to base adapter."""
        return self.base_adapter.is_leaf(node)
    
    async def calculate_timestamp(self, node: AsyncFileSystemNode, depth: int = 0) -> Optional[datetime]:
        """
        Calculate timestamp for a folder based on strategy.
        
        Args:
            node: The folder node
            depth: Current depth in tree (for optimization)
            
        Returns:
            Calculated timestamp or None
        """
        if not isinstance(node, AsyncFileSystemNode):
            return None
            
        path = node.path
        if not path.is_dir():
            return None
        
        if self.strategy == 'shallow':
            return await self._shallow_timestamp(path)
        elif self.strategy == 'deep':
            return await self._deep_timestamp(path)
        elif self.strategy == 'smart':
            return await self._smart_timestamp(path)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")
    
    async def _shallow_timestamp(self, path: Path) -> Optional[datetime]:
        """
        Calculate timestamp from immediate children only.
        
        Args:
            path: Directory path
            
        Returns:
            Latest timestamp from immediate children
        """
        latest = None
        
        try:
            for item in path.iterdir():
                try:
                    stat = item.stat()
                    mtime = datetime.fromtimestamp(stat.st_mtime)
                    
                    if latest is None or mtime > latest:
                        latest = mtime
                except (OSError, PermissionError):
                    continue
        except (OSError, PermissionError):
            return None
        
        return latest
    
    async def _deep_timestamp(self, path: Path) -> Optional[datetime]:
        """
        Calculate timestamp from all descendants recursively.
        
        Args:
            path: Directory path
            
        Returns:
            Latest timestamp from entire subtree
        """
        latest = None
        
        try:
            for root, dirs, files in os.walk(path):
                root_path = Path(root)
                
                # Check all items in this directory
                for item_name in dirs + files:
                    item_path = root_path / item_name
                    try:
                        stat = item_path.stat()
                        mtime = datetime.fromtimestamp(stat.st_mtime)
                        
                        if latest is None or mtime > latest:
                            latest = mtime
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            return None
        
        return latest
    
    async def _smart_timestamp(self, path: Path) -> Optional[datetime]:
        """
        Smart timestamp calculation - shallow for recent, deep for old.
        
        If folder was modified within threshold days, use shallow scan.
        Otherwise use deep scan to catch nested changes.
        
        Args:
            path: Directory path
            
        Returns:
            Calculated timestamp based on folder age
        """
        try:
            # Check folder's own modification time
            stat = path.stat()
            folder_mtime = datetime.fromtimestamp(stat.st_mtime)
            now = datetime.now()
            
            days_old = (now - folder_mtime).days
            
            # If recently modified, shallow scan is sufficient
            if days_old <= self.smart_threshold_days:
                return await self._shallow_timestamp(path)
            else:
                # Older folders need deep scan to catch nested changes
                return await self._deep_timestamp(path)
                
        except (OSError, PermissionError):
            return None
    
    def get_config(self) -> Dict[str, Any]:
        """Get adapter configuration."""
        return {
            'adapter': 'TimestampCalculation',
            'strategy': self.strategy,
            'smart_threshold_days': self.smart_threshold_days
        }