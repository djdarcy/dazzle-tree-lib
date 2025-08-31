# TreeLib - Universal Tree Traversal Library

TreeLib is a generic Python library for tree traversal and operations that can work with ANY tree structure - filesystem, XML, JSON, databases, or custom data structures.

## Vision

TreeLib provides a universal abstraction for tree operations, enabling developers to:
- Write tree traversal logic once and apply it to any tree structure
- Perform horizontal cuts (depth filtering) and vertical cuts (path filtering)
- Manage caching with completeness tracking
- Handle massive trees efficiently with lazy evaluation
- Validate configurations before execution

## Architecture

TreeLib follows the **Configuration → Execution Plan → Traversal** pattern:

1. **Configuration**: Define what you want (depth, filters, data requirements)
2. **Execution Plan**: Validate that it's possible and prepare for execution
3. **Traversal**: Execute the plan efficiently

### Key Components

- **TreeNode**: Abstract data container for any tree node
- **TreeAdapter**: Logic for navigating specific tree structures (the key to universality)
- **TraversalConfig**: User intent specification
- **ExecutionPlan**: Validation and coordination layer
- **Traversers**: Various traversal algorithms (BFS, DFS, etc.)
- **DataCollectors**: Strategies for extracting data from nodes

## Installation

```bash
pip install treelib
```

For development:
```bash
pip install -e .
```

## Quick Start

### Simple Usage

```python
from treelib import traverse_tree, FileSystemAdapter

# Simple traversal
adapter = FileSystemAdapter()
for node in traverse_tree(root, adapter, max_depth=3):
    print(node.identifier())
```

### Advanced Usage

```python
from treelib import TraversalConfig, ExecutionPlan, FileSystemAdapter
from treelib.config import DataRequirement, TraversalStrategy

# Configure traversal
config = TraversalConfig(
    strategy=TraversalStrategy.DEPTH_FIRST_POST,
    max_depth=5,
    data_requirements=DataRequirement.METADATA,
    exclude_filter=lambda n: n.name.startswith('.'),
    lazy_evaluation=True
)

# Create execution plan
adapter = FileSystemAdapter()
plan = ExecutionPlan(config, adapter)

# Execute traversal
for node, data in plan.execute(root):
    print(f"{node.identifier()}: {data}")
```

## Creating Custom Adapters

```python
from treelib import TreeAdapter, TreeNode

class MyCustomAdapter(TreeAdapter):
    def get_children(self, node: TreeNode) -> Iterator[TreeNode]:
        # Your logic for getting child nodes
        pass
    
    def get_parent(self, node: TreeNode) -> Optional[TreeNode]:
        # Your logic for getting parent node
        pass
```

## Library Ecosystem

TreeLib is part of a comprehensive toolkit for file and tree operations:

- **UNCtools**: Network path handling
- **TreeLib**: Generic tree traversal (this library)
- **FileLib**: File operations and metadata
- **HashLib**: Hashing and integrity checking

## Development Status

TreeLib is under active development. Current focus:
- [x] Core architecture design
- [ ] Basic implementation
- [ ] FileSystem adapter
- [ ] Test suite
- [ ] Documentation
- [ ] Performance optimization

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

## License

MIT License - see LICENSE file for details