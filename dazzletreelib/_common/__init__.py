"""Common components shared between sync and aio implementations.

This internal package contains non-I/O code that is identical between
both implementations. It should NOT be imported directly by users.

Components here include:
- Configuration classes (TraversalConfig)
- Data structures (non-I/O specific)
- Utility functions (pure computation, no I/O)

Important: This package must NEVER import from sync or aio to avoid
circular dependencies.
"""

# Re-export configuration components
from .config import (
    TraversalConfig,
    TraversalStrategy,
    DataRequirement,
    CacheStrategy,
    CacheCompleteness,
    FilterConfig,
    DepthConfig,
    PerformanceConfig,
)

__all__ = [
    'TraversalConfig',
    'TraversalStrategy',
    'DataRequirement',
    'CacheStrategy',
    'CacheCompleteness',
    'FilterConfig',
    'DepthConfig',
    'PerformanceConfig',
]