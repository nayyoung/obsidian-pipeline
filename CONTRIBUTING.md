# Contributing to Obsidian Pipeline

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/nayyoung/obsidian-pipeline.git
   cd obsidian-pipeline
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r obsidian-pipeline/requirements.txt
   ```

## Code Quality Standards

### Python Style
- Follow PEP 8 style guidelines
- Use meaningful variable and function names
- Add docstrings to all functions and classes
- Include type hints where appropriate

### Code Structure
- Keep functions focused and single-purpose
- Avoid deep nesting (max 3-4 levels)
- Use early returns to reduce complexity
- Handle errors explicitly, don't use bare `except`

### Security
- Never commit API keys or secrets
- Validate all user input
- Use parameterized queries/safe string formatting
- Follow principle of least privilege

## Adding Features

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clean, documented code
   - Add error handling
   - Include logging where appropriate

3. **Test your changes**
   - Test with actual conversation files
   - Test error cases (missing files, invalid input, etc.)
   - Verify security considerations

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add feature description"
   ```
   
   Use conventional commit messages:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation
   - `refactor:` for code refactoring
   - `test:` for adding tests
   - `chore:` for maintenance tasks

5. **Push and create a pull request**
   ```bash
   git push origin feature/your-feature-name
   ```

## Bug Reports

When reporting bugs, please include:
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages and logs
- Sample input files (sanitize sensitive data!)

## Feature Requests

When requesting features:
- Describe the use case
- Explain the expected behavior
- Consider backward compatibility
- Think about configuration needs

## Code Review Process

All contributions go through code review:
1. Automated checks run on PRs
2. Maintainer reviews code quality
3. Security implications are assessed
4. Feedback is provided for improvements
5. Once approved, PR is merged

## Areas for Contribution

### High Priority
- Test coverage improvements
- Error handling enhancements
- Documentation updates
- Performance optimizations

### Feature Ideas
- Support for additional AI platforms
- Better conflict detection
- Automated backups
- Web interface
- Batch processing improvements

### Documentation
- More examples
- Video tutorials
- Use case documentation
- API documentation

## Questions?

- Open a GitHub Discussion for general questions
- Open an Issue for bug reports
- Open a PR for code contributions

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
