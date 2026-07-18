# magnus

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21247825.svg)](https://doi.org/10.5281/zenodo.21247825)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-AGPL--3.0-green)



**magnus** is an experimental Python library for the computational analysis of discrete sequences and multidimensional time series using non-commutative Magnus algebras and the homological theory of $fr$-codes (Ivanov, Mikhailov, Pavutnitskiy).

The library provides a methodology to map sequential data into a finitely presented group $G = \langle V \mid R \rangle$, where a finite alphabet of discrete symbols acts as the generating set $V$, and their observed contextual or temporal transitions define the relations $R$. 

Using the Magnus expansion in free group rings, it constructs sparse matrices representing specific $fr$-ideals (e.g., $c = rr + frf$) and evaluates the exact dimension of the truncated factor algebra $f/c$ over the finite field $\mathbb{Z}_p$. 

**Current focus:** Detecting structural degradation regimes in multidimensional time series (sensor data, logs) and extracting topological invariants from text corpora. *Experimental — under active development.*

## Scientific Foundation

The mathematical framework of this library is an algorithmic implementation of the theory of $fr$-codes. The library acts as a computational solver: given a single group presentation $G = \langle V \mid R \rangle$ derived from data, it evaluates the quotient dimension $\dim(f/c)$ up to a specified Magnus degree.

According to Ivanov et al. (2020), taking the first derived limit $\lim^1$ of these functors over the full category of free group presentations $\text{Pres}(G)$ yields classical integral group homologies (e.g., $H_3(G, \mathbb{Z})$). While computing limits over the entire category $\text{Pres}(G)$ is computationally intractable for empirical data, **this library provides the exact finite-dimensional building block** — the functor value evaluated on a single, specific data-induced presentation.

### Key Reference:
*   **Ivanov, S. O., Mikhailov, R., & Pavutnitskiy, F. (2020).** *Limits, standard complexes and $fr$-codes.* Sbornik: Mathematics, 211(11), 1594-1622. Preprint available at [arXiv:1906.08793 [math.GR]](https://arxiv.org/abs/1906.08793).

## Key Features
*   **Homological Feature Selection:** A greedy forward selection algorithm that identifies an optimal discrete alphabet (generating set $V$) by iteratively maximizing the algebraic rank of the boundary matrix for the $rr + frf$ code. For NLP tasks, this isolates structural operators (e.g., prepositions, conjunctions) based purely on their topological contribution to the group presentation, bypassing naive frequency-based metrics.
*   **Non-Commutative Magnus Expansion:** Evaluates the cascading non-commutative Magnus expansion of group relations up to degree 4 within the augmentation ideal of the free group ring $\mathbb{Z}[F]$.
*   **Exact $\mathbb{Z}_p$ Rank Solver:** Employs a sparse Gaussian elimination algorithm over the finite field $\mathbb{Z}_p$ ($p = 10^9+7$) to compute exact algebraic ranks. This completely avoids numerical floating-point inaccuracies and the need for empirical thresholds.
*   **Memory Optimization:** Designed for sparse tensor operations to safely handle the exponential combinatorial dimension scaling inherent to free group rings.

## Installation
To install the library locally in editable development mode:

```bash
git clone https://github.com/Assistentus/magnus.git
cd magnus
pip install -e .
```

## Verification & Unit Tests
The mathematical soundness of the implementation is verified using strict algebraic inequalities derived from the foundational theory. In any finitely presented group:

1.  Since the ideal $c_1 = rr + frf + rff$ consists of monomials of length $\ge 2$, it is contained in $f^2$. Consequently, there is a natural surjection $f/c_1 \to f/f^2$. Since $\dim(f/f^2) = K$, the strict invariant holds: **$\dim(f/c_1) \ge K$** (the number of generators).
2.  Since the ideal $c_2 = rr + frf$ is a sub-ideal of $c_1$ ($c_2 \subset c_1$), there is a surjection $f/c_2 \to f/c_1$. Thus, the strict invariant holds: **$\dim(f/c_2) \ge \dim(f/c_1)$**.

To run the algebraic verification suite:

```bash
python -m pytest tests/test_core.py -v -s
```

## Usage Example
*Note: While the library is currently focused on time-series anomaly detection, text corpora provide the most intuitive example of mapping discrete sequences to a group presentation.*

```python
from magnus import TextPresentation, MagnusAlgebra, FRCodeRegistry, HomologySolver

# 1. Provide a discrete sequence (e.g., a text corpus)
text = "The man saw a house. The house stood on a hill. The man walked to the house."

# 2. Build the group presentation G = <V | R> (e.g., K=15 generators)
# This automatically runs Homological Feature Selection to extract the structural alphabet V
pres = TextPresentation(text, k_vocab=15)

# 3. Initialize the Magnus algebra up to degree 4
magnus = MagnusAlgebra(K=pres.k_vocab, degree=4)
r_generators = [magnus.expand_word(rel) for rel in pres.relations]

# 4. Build the matrix for the rr + frf ideal
# (Under lim^1 over Pres(G), this recovers H_3(G); here we compute its finite-dimensional truncation)
c_matrix = FRCodeRegistry.build_rr_frf(magnus, r_generators)

# 5. Evaluate the exact rank and quotient dimension over Z_p
solver = HomologySolver()
results = solver.evaluate(c_matrix, dim_f=magnus.dim)

print(f"Free space dimension: {results['dim_f']}")
print(f"Matrix rank:          {results['rank_c']}")
print(f"Factor dimension:     {results['dim_factor']} (strictly >= K)")
```

## Note on Performance
This open-source package provides a pure Python implementation of the sparse Gaussian elimination solver. It is mathematically exact and suitable for small-to-medium datasets (up to ~100 defining relations) for research, verification, and educational purposes. Processing large, dense sequences generates heavy algebraic systems that may exceed Python's optimal memory and execution constraints.

## License
This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

## Citation
If you use Magnus in scientific work, please cite:

**Khotinsky, M. (2026).** *Magnus (v0.1.0)*. Zenodo. https://doi.org/10.5281/zenodo.21247825
