# Contributing to DazzleTreeLib

Thank you for considering contributing to DazzleTreeLib! We welcome contributions from everyone.

## Code of Conduct

Please note that this project is released with a Contributor Code of Conduct.
By participating in this project you agree to abide by its terms.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates. When you create a bug report, please include as many details as possible:

- **Use a clear and descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide specific examples** to demonstrate the steps
- **Describe the behavior you observed** and what you expected
- **Include Python version, OS, and DazzleTreeLib version**
- **Include code samples** that demonstrate the issue

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:

- **Use a clear and descriptive title**
- **Provide a detailed description** of the suggested enhancement
- **Provide specific examples** to demonstrate the use case
- **Explain why this enhancement would be useful**
- **Consider if it fits with the universal adapter philosophy**

### Contributing Code

#### First Time Contributors

- Look for issues labeled `good first issue` or `help wanted`
- Read the [universal adapter documentation](docs/universal-adapters.md) to understand the architecture
- Review the [comparison with other libraries](docs/comparison.md) to understand positioning

#### Development Setup

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/DazzleTreeLib.git`
3. Create a virtual environment: `python -m venv venv`
4. Install in development mode: `pip install -e .[dev]`
5. Install git hooks: `./scripts/install-hooks.sh`

#### Pull Request Process

1. **Create a new branch** from `dev` (not `main`):
   ```bash
   git checkout dev
   git pull upstream dev
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**:
   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation as needed
   - Ensure your changes work with both sync and async APIs

3. **Test your changes**:
   ```bash
   python run_tests.py  # Run full test suite
   python run_tests.py --fast  # Quick tests only
   ```

4. **Update documentation**:
   - Update README.md if adding new features
   - Update CHANGELOG.md with your changes
   - Add examples if introducing new patterns
   - Update adapter documentation if relevant

5. **Commit your changes**:
   - Use clear, descriptive commit messages
   - Reference any related issues
   - The pre-commit hook will update version automatically

6. **Push and create PR**:
   - Push to your fork
   - Create PR against `dev` branch (not `main`)
   - Fill out the PR template completely
   - Link any related issues

### Development Guidelines

#### Code Style

- Follow PEP 8
- Use type hints for all new code
- Maintain sync/async API parity
- Document all public APIs
- Keep line length under 100 characters

#### Testing Requirements

- All new features must have tests
- Maintain or improve code coverage
- Test both sync and async implementations
- Include edge cases and error conditions

#### Adapter Development

When creating new adapters:

1. Inherit from appropriate base class (`TreeAdapter` or `AsyncTreeAdapter`)
2. Implement all required methods
3. Support both sync and async if possible
4. Document the adapter's purpose and usage
5. Add examples showing integration
6. Consider composability with existing adapters

See [universal adapter documentation](docs/universal-adapters.md) for details.

#### Performance Considerations

- Profile before optimizing
- Document performance characteristics
- Consider memory usage for large trees
- Test with various tree sizes
- Compare with native implementations

### Documentation

- Use clear, concise language
- Include code examples
- Update comparison tables if adding features
- Keep README focused, use separate docs for details
- Follow the progressive disclosure pattern

### Questions?

Feel free to:
- Open a discussion on GitHub
- Ask questions in issues
- Review existing documentation
- Check the [universal adapter guide](docs/universal-adapters.md)

## Recognition

Contributors will be recognized in:
- The project README acknowledgments
- Release notes for their contributions
- GitHub contributors page

Thank you for helping make DazzleTreeLib better!