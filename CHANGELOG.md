# Changelog

All notable changes to DazzleTreeLib will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2025-08-31

### Added
- **FastAsyncFileSystemAdapter** - New os.scandir-based adapter providing 9-12x performance improvement
- **StatCache** - Two-level caching system reducing redundant filesystem calls by 19-33%
- **Comprehensive optimization test suite** - 20 tests validating performance improvements
- **Fast adapter as default** - traverse_tree_async now uses fast adapter by default

### Performance Improvements
- **9-12x faster** with FastAsyncFileSystemAdapter using os.scandir's cached DirEntry
- **19-33% improvement** from stat caching eliminating duplicate syscalls
- **Memory efficient** scandir implementation with cached stat information
- **Optimized for folder-datetime-fix** integration scenarios

### Technical Details
- DirEntry objects from os.scandir provide cached stat information
- Two-level cache: local node cache + global stat cache with TTL
- Backwards compatible with use_fast_adapter parameter
- Comprehensive test coverage for all optimization paths

## [0.6.0] - 2025-08-31

### Added
- **Blazing Fast Async Implementation** - Complete async/await support with 3.3x+ speedup
- **Dual API Design** - Both sync and async interfaces with identical behavior
- **Batched Parallel Processing** - Intelligent batching for optimal I/O performance
- **Structured Concurrency** - TaskGroup-based implementation for robust error handling
- **Contract Testing** - Comprehensive test suite ensuring sync/async behavioral parity
- **Performance Benchmarks** - Validated 3.31x-3.70x speedup across various scenarios
- **Real-World Examples** - Production-ready examples including folder-datetime-fix
- **Modern Python Packaging** - Full pyproject.toml configuration with tool support

### Performance Improvements
- Tree traversal: **3.31x faster** for small to medium trees
- Parallel processing: **3.70x faster** for multiple trees
- Metadata collection: **1.92x faster** with async I/O
- Memory efficient streaming with AsyncIterator pattern
- Configurable batch size (256) and max concurrency (100)

### Technical Details
- Native async/await implementation (no thread pool executors)
- Semaphore-based concurrency control
- Zero-copy node creation for performance
- Proper structured concurrency with TaskGroup
- Full type hints for async interfaces

## [0.5.0] - 2025-08-30

### Added
- Initial synchronous implementation
- FileSystem adapter for directory traversal
- BFS and DFS traversal strategies
- Basic tree node abstractions
- Configuration system with DataRequirement enum
- Traversal depth limiting
- Memory-efficient iterator pattern

### Changed
- Renamed from TreeLib to DazzleTreeLib
- Improved package structure with sync/aio separation

## [0.4.0] - 2025-08-29

### Added
- Core architecture design
- Abstract base classes for adapters
- TreeNode abstraction
- Initial test framework

## [0.3.0] - 2025-08-28

### Added
- Project initialization
- Basic project structure
- Development environment setup
- Initial documentation

## [0.2.0] - 2025-08-27

### Added
- Conceptual design phase
- API design exploration
- Performance requirements definition

## [0.1.0] - 2025-08-26

### Added
- Project inception
- Initial requirements gathering
- Technology stack selection

---

## Upcoming Features (Roadmap)

### Phase 2 (This Week)
- Progress callbacks for long operations
- Migration guide from sync to async
- GitHub Actions CI/CD pipeline
- Performance tuning guide

### Phase 3 (Next Sprint)
- Caching layer for repeated traversals
- Query DSL for intuitive filtering
- Tree diff functionality
- Comprehensive API documentation

### Phase 4 (Future)
- Plugin system for extensibility
- Virtual tree adapters (S3, Database, API)
- Auto-optimization for hardware
- Advanced serialization support