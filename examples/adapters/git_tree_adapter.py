#!/usr/bin/env python3
"""
Complete example of a custom adapter for Git repository trees.

This example shows how to create both sync and async adapters for traversing
Git repository structure, demonstrating all the key concepts from the docs.
"""

import asyncio
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, AsyncIterator, Optional, Dict, Any, List
import sys

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dazzletreelib.sync.core.nodes import TreeNode
from dazzletreelib.sync.core.adapters import TreeAdapter
from dazzletreelib.aio.core.nodes import AsyncTreeNode
from dazzletreelib.aio.core.adapters import AsyncTreeAdapter


# ============================================================================
# Synchronous Implementation
# ============================================================================

@dataclass
class GitNode(TreeNode):
    """Node representing a file or directory in a Git repository."""
    
    repo_path: Path
    relative_path: str
    node_type: str  # 'tree' or 'blob'
    sha: str
    
    def identifier(self) -> str:
        """Unique identifier using SHA."""
        return self.sha
    
    def is_leaf(self) -> bool:
        """Blobs are leaves, trees are not."""
        return self.node_type == 'blob'
    
    @property
    def path(self) -> Path:
        """Full path to this item."""
        return self.repo_path / self.relative_path
    
    @property
    def name(self) -> str:
        """Just the name of this item."""
        return Path(self.relative_path).name
    
    def size(self) -> Optional[int]:
        """Get size of blob from Git."""
        if self.node_type != 'blob':
            return None
        
        try:
            result = subprocess.run(
                ['git', '-C', str(self.repo_path), 'cat-file', '-s', self.sha],
                capture_output=True,
                text=True,
                check=True
            )
            return int(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError):
            return None
    
    def metadata(self) -> Dict[str, Any]:
        """Get Git metadata for this node."""
        return {
            'type': self.node_type,
            'sha': self.sha,
            'path': self.relative_path,
            'name': self.name
        }


class GitTreeAdapter(TreeAdapter):
    """Adapter for traversing Git repository structure."""
    
    def __init__(self, repo_path: Path, ref: str = 'HEAD'):
        """Initialize Git adapter.
        
        Args:
            repo_path: Path to Git repository
            ref: Git reference to traverse (default: HEAD)
        """
        self.repo_path = Path(repo_path)
        self.ref = ref
        
        # Verify it's a Git repo
        if not (self.repo_path / '.git').exists():
            raise ValueError(f"{repo_path} is not a Git repository")
    
    def get_children(self, node: GitNode) -> Iterator[GitNode]:
        """Get children of a Git tree node."""
        if node.node_type != 'tree':
            return  # Blobs have no children
        
        try:
            # Use git ls-tree to get children
            result = subprocess.run(
                ['git', '-C', str(self.repo_path), 'ls-tree', node.sha],
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                # Parse: mode type sha\tname
                parts = line.split('\t')
                if len(parts) != 2:
                    continue
                
                mode_type_sha = parts[0].split()
                if len(mode_type_sha) != 3:
                    continue
                
                mode, obj_type, sha = mode_type_sha
                name = parts[1]
                
                # Convert Git type to our type
                node_type = 'tree' if obj_type == 'tree' else 'blob'
                
                # Build child path
                child_path = (
                    f"{node.relative_path}/{name}"
                    if node.relative_path
                    else name
                )
                
                yield GitNode(
                    repo_path=self.repo_path,
                    relative_path=child_path,
                    node_type=node_type,
                    sha=sha
                )
        
        except subprocess.CalledProcessError:
            # Error getting children, return empty
            return
    
    def get_parent(self, node: GitNode) -> Optional[GitNode]:
        """Get parent of a Git node (not efficiently implemented)."""
        # Git doesn't track parents directly in tree structure
        # Would need to traverse from root to find parent
        return None
    
    def create_root_node(self) -> GitNode:
        """Create root node for the repository."""
        try:
            # Get tree SHA for the ref
            result = subprocess.run(
                ['git', '-C', str(self.repo_path), 'rev-parse', f'{self.ref}^{{tree}}'],
                capture_output=True,
                text=True,
                check=True
            )
            tree_sha = result.stdout.strip()
            
            return GitNode(
                repo_path=self.repo_path,
                relative_path='',
                node_type='tree',
                sha=tree_sha
            )
        
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Failed to get tree for {self.ref}: {e}")


# ============================================================================
# Asynchronous Implementation
# ============================================================================

@dataclass
class AsyncGitNode(AsyncTreeNode):
    """Async node for Git repository items."""
    
    repo_path: Path
    relative_path: str
    node_type: str
    sha: str
    
    async def identifier(self) -> str:
        """Return SHA as identifier."""
        return self.sha
    
    async def is_leaf(self) -> bool:
        """Check if this is a blob (leaf)."""
        return self.node_type == 'blob'
    
    @property
    def path(self) -> Path:
        """Full path to this item."""
        return self.repo_path / self.relative_path
    
    @property
    def name(self) -> str:
        """Just the name."""
        return Path(self.relative_path).name
    
    async def size(self) -> Optional[int]:
        """Get blob size asynchronously."""
        if self.node_type != 'blob':
            return None
        
        try:
            proc = await asyncio.create_subprocess_exec(
                'git', '-C', str(self.repo_path), 'cat-file', '-s', self.sha,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            if proc.returncode == 0:
                return int(stdout.decode().strip())
        except (ValueError, OSError):
            pass
        
        return None
    
    async def metadata(self) -> Dict[str, Any]:
        """Get metadata asynchronously."""
        size = await self.size() if self.node_type == 'blob' else None
        
        return {
            'type': self.node_type,
            'sha': self.sha,
            'path': self.relative_path,
            'name': self.name,
            'size': size
        }


class AsyncGitTreeAdapter(AsyncTreeAdapter):
    """Async adapter for Git with batched processing."""
    
    def __init__(
        self,
        repo_path: Path,
        ref: str = 'HEAD',
        batch_size: int = 256,
        max_concurrent: int = 100
    ):
        """Initialize async Git adapter.
        
        Args:
            repo_path: Path to repository
            ref: Git reference
            batch_size: Process children in batches
            max_concurrent: Max concurrent operations
        """
        self.repo_path = Path(repo_path)
        self.ref = ref
        self.batch_size = batch_size
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        if not (self.repo_path / '.git').exists():
            raise ValueError(f"{repo_path} is not a Git repository")
    
    async def get_children(self, node: AsyncGitNode) -> AsyncIterator[AsyncGitNode]:
        """Get children with batched async processing."""
        if node.node_type != 'tree':
            return
        
        # Get all children info first
        children_data = await self._fetch_children_data(node.sha)
        
        # Process in batches
        for i in range(0, len(children_data), self.batch_size):
            batch = children_data[i:i + self.batch_size]
            
            # Create nodes in parallel within batch
            async with asyncio.TaskGroup() as tg:
                tasks = []
                for child_info in batch:
                    task = tg.create_task(self._create_child_node(
                        node,
                        child_info
                    ))
                    tasks.append(task)
            
            # Yield completed nodes
            for task in tasks:
                child = await task
                if child:
                    yield child
    
    async def _fetch_children_data(self, tree_sha: str) -> List[Dict]:
        """Fetch children data from Git."""
        async with self.semaphore:
            proc = await asyncio.create_subprocess_exec(
                'git', '-C', str(self.repo_path), 'ls-tree', tree_sha,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            if proc.returncode != 0:
                return []
            
            children = []
            for line in stdout.decode().strip().split('\n'):
                if not line:
                    continue
                
                parts = line.split('\t')
                if len(parts) != 2:
                    continue
                
                mode_type_sha = parts[0].split()
                if len(mode_type_sha) != 3:
                    continue
                
                children.append({
                    'mode': mode_type_sha[0],
                    'type': mode_type_sha[1],
                    'sha': mode_type_sha[2],
                    'name': parts[1]
                })
            
            return children
    
    async def _create_child_node(
        self,
        parent: AsyncGitNode,
        child_info: Dict
    ) -> Optional[AsyncGitNode]:
        """Create a child node asynchronously."""
        async with self.semaphore:
            node_type = 'tree' if child_info['type'] == 'tree' else 'blob'
            
            child_path = (
                f"{parent.relative_path}/{child_info['name']}"
                if parent.relative_path
                else child_info['name']
            )
            
            return AsyncGitNode(
                repo_path=self.repo_path,
                relative_path=child_path,
                node_type=node_type,
                sha=child_info['sha']
            )
    
    async def create_root_node(self) -> AsyncGitNode:
        """Create root node asynchronously."""
        proc = await asyncio.create_subprocess_exec(
            'git', '-C', str(self.repo_path), 'rev-parse', f'{self.ref}^{{tree}}',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise ValueError(f"Failed to get tree: {stderr.decode()}")
        
        tree_sha = stdout.decode().strip()
        
        return AsyncGitNode(
            repo_path=self.repo_path,
            relative_path='',
            node_type='tree',
            sha=tree_sha
        )


# ============================================================================
# Usage Examples
# ============================================================================

def sync_example():
    """Example of using synchronous Git adapter."""
    from dazzletreelib.sync import traverse_tree
    
    # Create adapter for current repository
    adapter = GitTreeAdapter(Path.cwd())
    root = adapter.create_root_node()
    
    print("Synchronous Git Tree Traversal")
    print("=" * 50)
    
    file_count = 0
    total_size = 0
    
    for node, depth in traverse_tree(root, adapter, max_depth=3):
        indent = "  " * depth
        
        if node.is_leaf():
            size = node.size() or 0
            total_size += size
            file_count += 1
            print(f"{indent}📄 {node.name} ({size} bytes)")
        else:
            print(f"{indent}📁 {node.name}/")
    
    print(f"\nTotal: {file_count} files, {total_size:,} bytes")


async def async_example():
    """Example of using asynchronous Git adapter."""
    from dazzletreelib.aio import traverse_tree_async
    
    # Create async adapter with batching
    adapter = AsyncGitTreeAdapter(
        Path.cwd(),
        batch_size=100,
        max_concurrent=50
    )
    root = await adapter.create_root_node()
    
    print("\nAsynchronous Git Tree Traversal (3x+ faster!)")
    print("=" * 50)
    
    file_count = 0
    total_size = 0
    
    # Note: async version doesn't return depth directly
    async for node in traverse_tree_async(root, adapter=adapter, max_depth=3):
        if await node.is_leaf():
            size = await node.size() or 0
            total_size += size
            file_count += 1
            print(f"📄 {node.name} ({size} bytes)")
        else:
            print(f"📁 {node.name}/")
    
    print(f"\nTotal: {file_count} files, {total_size:,} bytes")


async def performance_comparison():
    """Compare sync vs async performance."""
    import time
    
    print("\nPerformance Comparison")
    print("=" * 50)
    
    # Sync timing
    start = time.perf_counter()
    sync_example()
    sync_time = time.perf_counter() - start
    
    # Async timing
    start = time.perf_counter()
    await async_example()
    async_time = time.perf_counter() - start
    
    print(f"\nSync time: {sync_time:.3f}s")
    print(f"Async time: {async_time:.3f}s")
    print(f"Speedup: {sync_time / async_time:.2f}x")


if __name__ == "__main__":
    print("Git Tree Adapter Example")
    print("=" * 50)
    
    # Check if we're in a Git repository
    if not (Path.cwd() / '.git').exists():
        print("Error: Not in a Git repository!")
        print("Please run this from a Git repository directory.")
        sys.exit(1)
    
    # Run synchronous example
    sync_example()
    
    # Run asynchronous example
    asyncio.run(async_example())
    
    # Run performance comparison
    asyncio.run(performance_comparison())