# magnus

**magnus** is an experimental Python library for the computational analysis of discrete sequences and multidimensional time series using non-commutative Magnus algebras and the homological theory of $fr$-codes (Ivanov, Mikhailov, Pavutnitskiy).

The library provides a methodology to map sequential data into a finitely presented group $G = \langle V \mid R \rangle$, where a finite alphabet of discrete symbols acts as the generating set $V$, and their observed contextual or temporal transitions define the relations $R$. Using the Magnus expansion in free group rings, it constructs sparse boundary matrices associated with specific $fr$-codes (e.g., $rr+frf$), whose derived limits are isomorphic to integral group homologies (e.g., $H_3(G)$), evaluating their exact ranks over the finite field $\mathbb{Z}_p$.

Current focus: detecting structural degradation regimes in multidimensional time series (sensor data, logs) and extracting topological invariants from text corpora. Experimental — under active development.

## Scientific Foundation
The mathematical framework of this library is an algorithmic implementation of the theory of $fr$-codes. The library acts as a computational solver: given a group presentation $G$, it evaluates the boundary operators whose first derived limits over the category of free group presentations $\text{Pres}(G)$ compute specific homological invariants.

**Key Reference:**
> Ivanov, S. O., Mikhailov, R., & Pavutnitskiy, F. (2020). Limits, standard complexes and $fr$-codes. *Sbornik: Mathematics*, 211(11), 1594-1622. Preprint available at [arXiv:1906.08793 [math.GR]](https://arxiv.org/abs/1906.08793).

## Key Features

*   **Homological Feature Selection:** A greedy forward selection algorithm that identifies an optimal discrete alphabet (generating set $V$) by iteratively maximizing the algebraic rank of the boundary matrix for the $rr+frf$ code. For NLP tasks, this naturally isolates structural operators (e.g., prepositions, conjunctions) based purely on their topological contribution to the group presentation, bypassing traditional frequency-based metrics.
*   **Non-Commutative Magnus Expansion:** Evaluates the non-commutative Magnus expansion of group relations up to degree 4 within the augmentation ideal of the free group ring $\mathbb{Z}[F]$.
*   **Exact $\mathbb{Z}_p$ Rank Solver:** Employs a sparse Gaussian elimination algorithm over the finite field $\mathbb{Z}_p$ ($p=10^9+7$) to compute exact algebraic ranks. This completely avoids numerical floating-point inaccuracies and the need for empirical thresholds.
*   **Memory Optimization:** Designed for sparse tensor operations to safely handle the combinatorial dimension scaling inherent to free group rings.

## Installation

To install the library locally in editable development mode:

```bash
git clone https://github.com/Assistentus/magnus.git
cd magnus
pip install -e .
```

## Verification & Unit Tests

The mathematical soundness of the implementation is verified using strict algebraic inequalities derived from the foundational theory. In any finitely presented group:
1. The dimension of the quotient space (homological factor) associated with the $fr$-code $c_1 = rr + frf + rff$ (which corresponds to $H_2(G, G_{ab})$) must be strictly greater than or equal to $K$ (the number of generators).
2. The dimension of the factor for the sub-code $c_2 = rr + frf$ (which corresponds to $H_3(G)$) must be greater than or equal to the dimension of the $c_1$ factor.

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
# This automatically runs the Homological Feature Selection to extract the structural alphabet V
pres = TextPresentation(text, k_vocab=15)

# 3. Initialize the Magnus algebra up to degree 4
magnus = MagnusAlgebra(K=pres.k_vocab, degree=4)
r_generators = [magnus.expand_word(rel) for rel in pres.relations]

# 4. Build the boundary matrix for the rr + frf code (corresponding to H_3 homology)
c_matrix = FRCodeRegistry.build_rr_frf(magnus, r_generators)

# 5. Evaluate the exact rank and quotient dimension over Z_p
solver = HomologySolver()
results = solver.evaluate(c_matrix, dim_f=magnus.dim)

print(f"Free space dimension: {results['dim_f']}")
print(f"Boundary matrix rank: {results['rank_c']}")
print(f"Homological factor:   {results['dim_factor']} (strictly >= K)")
```

## Note on Performance
This open-source package provides a pure Python implementation of the sparse Gaussian elimination solver. It is mathematically exact and suitable for small-to-medium datasets (up to ~100 defining relations) for research, verification, and educational purposes. Processing large, dense sequences generates heavy algebraic systems that may exceed Python's optimal memory and execution constraints.

## License
This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).
