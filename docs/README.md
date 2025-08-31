# DazzleTreeLib Documentation

Welcome to the DazzleTreeLib documentation! This guide will help you understand how to use the library, extend it with custom adapters, and maintain compatibility between sync and async implementations.

## Table of Contents

1. [**Getting Started**](getting-started.md) - Installation and basic usage
2. [**API Reference**](api-reference.md) - Complete API documentation
3. [**Architecture Overview**](architecture.md) - Understanding the library design
4. [**Adapter Development Guide**](adapter-development.md) - Creating custom adapters
5. [**Sync/Async Compatibility**](sync-async-compatibility.md) - Maintaining dual API support
6. [**Performance Guide**](performance.md) - Optimization and benchmarking
7. [**Examples**](../examples/) - Complete working examples

## Quick Links

- [Creating a Custom Adapter](adapter-development.md#creating-a-custom-adapter)
- [Sync vs Async API Differences](sync-async-compatibility.md#api-differences)
- [Performance Benchmarks](performance.md#benchmarks)
- [Migration Guide](getting-started.md#migrating-from-sync-to-async)

## Core Concepts

### Tree Abstractions

DazzleTreeLib provides universal abstractions for tree operations:

- **TreeNode**: Represents any node in a tree structure
- **TreeAdapter**: Defines how to navigate a specific tree type
- **Traverser**: Implements traversal algorithms (BFS, DFS, etc.)
- **DataCollector**: Extracts data from nodes during traversal

### Dual API Design

The library provides both synchronous and asynchronous APIs:

```python
# Synchronous
from dazzletreelib.sync import traverse_tree

# Asynchronous (3x+ faster!)
from dazzletreelib.aio import traverse_tree_async
```

### Extensibility

Create adapters for any tree structure:
- Filesystems (local, network, cloud)
- Databases (hierarchical, graph)
- APIs (REST, GraphQL)
- Data structures (JSON, XML, AST)

## Getting Help

- [GitHub Issues](https://github.com/yourusername/DazzleTreeLib/issues)
- [Discussions](https://github.com/yourusername/DazzleTreeLib/discussions)
- [Examples](../examples/)

## Contributing

See our [Adapter Development Guide](adapter-development.md) to learn how to contribute new adapters to the library.