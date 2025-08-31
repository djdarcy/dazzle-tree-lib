"""Configuration re-export for backward compatibility.

This module maintains backward compatibility by re-exporting
configuration components from the _common package.
"""

# Re-export everything from _common.config
from .._common.config import *

# For explicit imports
from .._common.config import (
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