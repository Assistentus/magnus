```markdown
# Contributing to `magnus`

Thank you for your interest in contributing to `magnus`. `magnus` is an experimental computational framework bridging non-commutative algebra ($fr$-codes, Magnus expansions) and sequence analysis. We welcome bug reports, feature requests, documentation improvements, and code contributions.

## Table of Contents
1. [Code of Conduct](#code-of-conduct)
2. [How to Report a Bug](#how-to-report-a-bug)
3. [How to Suggest a Feature](#how-to-suggest-a-feature)
4. [Local Development Setup](#local-development-setup)
5. [Testing and Algebraic Invariants](#testing-and-algebraic-invariants)
6. [Pull Request Process](#pull-request-process)

## Code of Conduct
By participating in this project, please maintain professional, clear, and respectful communication.

## How to Report a Bug
If you find a bug, please create an Issue on GitHub. A helpful bug report should include:
- A clear, descriptive title.
- The versions of `magnus`, Python, and Rust you are using.
- A minimal reproducible code example (MRE).
- The expected behavior vs. the actual behavior.
- Any relevant error logs or tracebacks.

## How to Suggest a Feature
When proposing a new feature (e.g., a new $fr$-code matrix generator or solver optimization):
- Open an Issue describing the proposed feature.
- Explain the scientific or computational need. If based on a specific homological theorem, please provide the reference or arXiv link.
- Wait for feedback before writing significant amounts of code.

## Local Development Setup

`magnus` is a hybrid Python/Rust library. To set up your local development environment:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Assistentus/magnus.git
   cd magnus
   ```

2. **Set up a Python virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install the Rust toolchain:**
   If you don't have Rust installed, download it via `rustup` (required for building the `fr_rank_rs` solver engine):
   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   ```

4. **Install the library in editable mode with development dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -e .
   pip install pytest
   ```

## Testing and Algebraic Invariants

`magnus` relies on strict algebraic inequalities derived from the theory of $fr$-codes to verify its core engine. Before submitting any code, please run the test suite to ensure mathematical invariants are maintained:

```bash
python -m pytest tests/ -v -s
```

If you add a new algorithmic feature, please include a corresponding test in the `tests/` directory.

## Pull Request Process

1. **Fork the repository** and create your branch from `main`.
   ```bash
   git checkout -b feature/my-new-algorithm
   ```
2. **Write your code** and ensure it follows standard Python conventions (PEP 8). For Rust code, please run `cargo fmt`.
3. **Add tests** for any new logic.
4. **Update the documentation** (README.md or docstrings) if you change the API.
5. **Run the test suite** locally and ensure all tests pass.
6. **Submit a Pull Request (PR)** targeting the `main` branch. 
7. In the PR description, link to any relevant Issues and describe what changes were made.

Your PR will be reviewed as soon as possible. Thank you for your contributions.
```
