#!/usr/bin/env python3
"""
ONE-OFF TEST: Proposed semantic change (NOT IMPLEMENTED)

Related to: GitHub Issue #37 - Node tracking semantic confusion
Created: 2025-09-15 during semantic redesign investigation
Purpose: Document proposed alternative approach to node tracking

Connected to:
- SmartCachingAdapter implementation (the actual solution we chose)
- tests/test_smart_caching_adapter.py (tests the solution we implemented)
- modified_datetime_fix integration issues

Context:
This file documents an ALTERNATIVE approach we considered but DID NOT implement.
Instead of tracking nodes when they're yielded as children (discovery), we chose
to create SmartCachingAdapter with explicit was_discovered() vs was_expanded() methods.

The approach documented here would have changed CompletenessAwareCacheAdapter's
semantics, which would have broken backward compatibility. Our actual solution
(SmartCachingAdapter) provides clean semantics without breaking existing code.

Note: This is documentation only - the proposed changes were NOT made.

Historical value: Shows the thinking process during semantic redesign.
"""

# The proposed change to cache_completeness_adapter.py:

# In get_children method, after yielding each child:

"""
# Fast mode path around line 406-408:
async for child in self.base_adapter.get_children(node):
    children.append(child)

    # NEW: Track the child as visited when yielded
    if self.should_track_nodes and hasattr(child, 'path'):
        child_path = child.path if hasattr(child, 'path') else str(child)
        # Track at depth 0 since we're not expanding this child yet
        self._track_node_visit_impl(str(child_path), 0)

    yield child

# Safe mode path around line 466-467:
async for child in self.base_adapter.get_children(node):
    children_list.append(child)

    # NEW: Track the child as visited when yielded
    if self.should_track_nodes and hasattr(child, 'path'):
        child_path = child.path if hasattr(child, 'path') else str(child)
        # Track at depth 0 since we're not expanding this child yet
        self._track_node_visit_impl(str(child_path), 0)

    yield child
"""

print("Proposed semantic change:")
print("  OLD: Track nodes when get_children() is called on them (expansion)")
print("  NEW: Track nodes when they're yielded as children (discovery)")
print("")
print("Benefits:")
print("  1. Matches modified_datetime_fix semantics")
print("  2. More intuitive - 'visited' means encountered during traversal")
print("  3. Nodes at max depth are properly tracked")
print("")
print("Drawbacks:")
print("  1. Changes existing semantics")
print("  2. Might affect other users of DazzleTreeLib")
print("  3. Slight performance impact from tracking more nodes")