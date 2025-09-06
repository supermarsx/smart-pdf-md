# Contribution Guide

## Code Style
- Target Python **3.11+**.
- Follow `ruff` with a line length of **100**.

## Required Checks
Run the following commands before committing:

```bash
ruff check
ruff format --check
pytest -q
```

## Commit Conventions
- Use concise, imperative commit messages (e.g., `feat: add feature`).
- Each commit should represent a logical change.

## Cross-Platform Support
- Ensure all scripts and tests run on Linux, macOS, and Windows.
- Executables are built using **PyInstaller**.
