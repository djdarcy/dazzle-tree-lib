# DazzleTreeLib Documentation

Welcome to the DazzleTreeLib documentation! This guide will help you understand how to use the library, extend it with custom adapters, and maintain compatibility between sync and async implementations.

## Table of Contents

### Core Documentation
1. [**Getting Started**](getting-started.md) - Installation and basic usage
2. [**API Reference**](api-reference.md) - Complete API documentation
3. [**Architecture Overview**](architecture.md) - Understanding the library design

### Caching System
4. [**Caching Basics**](caching-basics.md) - 🆕 Beginner-friendly introduction to caching
5. [**Caching Architecture**](caching.md) - 🆕 Advanced caching details and configuration

### Development Guides
6. [**Adapter Development Guide**](adapter-development.md) - Creating custom adapters
7. [**Sync/Async Compatibility**](sync-async-compatibility.md) - Maintaining dual API support
8. [**Performance Guide**](performance.md) - Optimization and benchmarking

### Additional Resources
9. [**Examples**](../examples/) - Complete working examples
10. [**Node Tracking Optimization**](node-tracking-optimization.md) - Memory optimization history

## Quick Links

### 🆕 Caching Documentation
- [**New to Caching?**](caching-basics.md) - Start here for concepts and examples
- [**Configure Caching**](caching.md#configuration-options) - Settings and options
- [**Caching Examples**](caching-basics.md#real-world-example-scanning-your-music-library) - Real-world usage
- [**Performance Tuning**](caching.md#performance-tuning) - Optimize cache performance

### Development
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