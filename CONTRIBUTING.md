```markdown
# Contributing to `magnus`

First off, thank you for considering contributing to `magnus`! 

It's people like you that make open-source software such a great community for researchers and developers. `magnus` is an experimental computational framework bridging non-commutative algebra ($fr$-codes, Magnus expansions) and data science. We welcome contributions of all kinds: bug reports, feature requests, documentation improvements, and code patches.

## Table of Contents
1. [Code of Conduct](#code-of-conduct)
2. [How to Report a Bug](#how-to-report-a-bug)
3. [How to Suggest a Feature](#how-to-suggest-a-feature)
4. [Local Development Setup](#local-development-setup)
5. [Testing and Algebraic Invariants](#testing-and-algebraic-invariants)
6. [Pull Request Process](#pull-request-process)

## Code of Conduct
By participating in this project, you agree to abide by friendly, professional, and respectful communication. We are a collaborative community of mathematicians, data scientists, and engineers.

## How to Report a Bug
If you find a bug, please create an Issue on GitHub. A good bug report should include:
- A clear, descriptive title.
- The version of `magnus`, Python, and Rust you are using.
- A minimal reproducible code example (MRE).
- The expected behavior vs. the actual behavior.
- Any relevant error logs or tracebacks.

## How to Suggest a Feature
Mathematical and algorithmic suggestions are highly encouraged! When proposing a new feature (e.g., a new $fr$-code matrix generator or a different field solver):
- Open an Issue describing the proposed feature.
- Explain the scientific or computational need (if based on a specific homological theorem, please provide the reference or arXiv link).
- Wait for feedback from the maintainers before writing significant amounts of code.

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
   If you don't have Rust installed, download it via `rustup` (required for building the `fr_rank_rs` fast solver engine):
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

Because `magnus` is a mathematical solver, ensuring absolute theoretical fidelity is our top priority. We use strict algebraic inequalities derived from the theory of $fr$-codes to verify the core engines.

Before submitting any code, you **must** run the test suite to ensure no mathematical invariants are broken:

```bash
python -m pytest tests/ -v -s
```

If you add a new algorithmic feature, please write a corresponding test in the `tests/` directory. If you are touching the solver or Magnus algebra generation, ensure that the invariants (e.g., $\dim(f/c) \ge K$) still hold.

## Pull Request Process

1. **Fork the repository** and create your branch from `main`.
   ```bash
   git checkout -b feature/my-new-algorithm
   ```
2. **Write your code** and ensure it follows standard Python conventions (PEP 8). For Rust code, please run `cargo fmt`.
3. **Add tests** for any new logic.
4. **Update the documentation** (README.md or docstrings) if you are changing the API.
5. **Run the test suite** locally and ensure everything passes.
6. **Submit a Pull Request (PR)** targeting the `main` branch. 
7. In the PR description, link to any relevant Issues and clearly describe what changes were made and why.

Once submitted, your PR will be reviewed by the maintainers. We might suggest some tweaks or improvements. Once everything looks good, it will be merged. 

Thank you for helping us make `magnus` better!
```
