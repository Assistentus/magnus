---
title: 'magnus: A Python/Rust framework for non-commutative structural analysis of discrete sequences via fr-codes'
tags:
  - Python
  - Rust
  - topological data analysis
  - non-commutative algebra
  - group theory
  - time series analysis
authors:
  - name: Maksim Khotinsky
    orcid: 0009-0004-1456-1033
    affiliation: 1
affiliations:
 - name: Independent Researcher, Moscow, Russian Federation
   index: 1
date: 23 August 2026
bibliography: paper.bib
---

# Summary

`magnus` is an experimental computational library designed for the structural analysis of discrete sequences and multidimensional time series. It implements the homological theory of $fr$-codes [@ivanov2020limits], providing a deterministic algebraic method for sequence analysis. The library maps empirical sequential data into finitely presented groups $G = \langle V \mid R \rangle$, constructs non-commutative Magnus expansions [@magnus1937beziehungen] up to a specified degree, and evaluates exact algebraic ranks over finite fields to extract structural invariants.

# Statement of need

Traditional approaches to sequential data analysis, such as frequency-based metrics (TF-IDF) or Markov chains, often overlook global structural grammar. While recent advancements in abstract algebra have linked the ideals of free group rings to classical integral group homologies, computing derived limits over the category of group presentations remains computationally intractable for empirical datasets. 

There is currently no accessible computational solver bridging this area of homological algebra with applied data science. `magnus` addresses this gap by providing an exact, finite-dimensional truncation solver. It enables researchers to translate discrete transitions into group presentations and track factor dimension drops as topological constraints emerge in the data.

# Software Architecture

The framework handles the combinatorial complexity inherent to free group rings through three core components:

1. **Homological Feature Selection:** A greedy forward selection algorithm that identifies the optimal generating set $V$ by maximizing the algebraic rank of the boundary matrix for the $rr + frf$ code. This isolates structural states based on their topological contribution.
2. **Magnus Expansion Engine:** The `MagnusAlgebra` module embeds the free group into a formal power series ring. Basis indices are computed on-the-fly in $O(d)$ time to prevent memory exhaustion when working with high-degree truncations.
3. **Exact Sparse $\mathbb{Z}_p$ Solver:** To avoid floating-point inaccuracies, the library computes exact algebraic ranks over the finite field $\mathbb{Z}_p$ ($p = 10^9 + 7$). The core solver is implemented as a Rust extension (`fr_rank_rs`) using `PyO3` for performance, with a mathematically equivalent pure-Python fallback for cross-platform compatibility.

# AI Disclosure

In accordance with JOSS guidelines, the author discloses the use of generative AI tools (LLMs) for code refactoring, generating unit test templates, and drafting standard repository documentation. All core algorithmic logic, architectural decisions, and mathematical implementations are original human work and have been verified by the author.

# Acknowledgements

The author acknowledges the foundational work of Sergei O. Ivanov, Roman Mikhailov, and Fedor Pavutnitskiy on the theory of $fr$-codes, which provided the theoretical basis for this computational tool.

# References
