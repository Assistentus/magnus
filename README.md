

# magnus

**magnus** is an experimental Python library for the computational analysis of discrete sequences using non-commutative Magnus algebras and the homological theory of fr-codes (Ivanov, Mikhailov, Pavutnitskiy).

The library models sequential data as a finitely presented group G = ⟨V | R⟩, where tokens act as generators (V) and their contextual relations form the relators (R). Using the Magnus expansion in free group rings, it constructs sparse boundary matrices for H₂ and H₃ group homology and computes exact ranks over Z_p.

Current focus: detecting structural changes in multidimensional time series (sensor data, logs) through the evolution of homological invariants. Experimental — under active development.

---

## Scientific Foundation

The mathematical framework of this library is an algorithmic implementation of the theory of $fr$-codes developed by S. O. Ivanov, R. Mikhailov, and F. Pavutnitskiy. The invariants computed represent the derived functors of limits over categories of free presentations of groups.

### Key Reference:
*   **Ivanov, S. O., Mikhailov, R., & Pavutnitskiy, F. (2020).** *Limits, standard complexes and $fr$-codes.* Sbornik: Mathematics, 211(11), 1594-1622. 
    Preprint available at [arXiv:1906.08793 [math.GR]](https://arxiv.org/abs/1906.08793).

---

## Key Features

*   **Homological Feature Selection:** An algorithmic vocabulary selector (Greedy Forward Selection) that extracts generators by iteratively maximizing the algebraic rank of the $H_3$ ($rr+frf$) boundary matrix. This extracts structural operators (negations, prepositions, conjunctions, pronouns) based purely on their topological contribution, bypassing traditional frequency-based metrics.
*   **Non-Commutative Magnus Expansion:** Evaluates the cascading Magnus expansion of relations up to degree 4 in the augmentation ideal of the free group ring.
*   **Exact $\mathbb{Z}_p$ Rank Solver:** Employs a sparse Gaussian elimination algorithm over finite fields ($\mathbb{Z}_p$, $p = 10^9+7$) to compute exact algebraic ranks, completely avoiding numerical floating-point inaccuracies and heuristic thresholds.
*   **Memory Optimization:** Designed for sparse operations to safely handle combinatorial dimension scaling.

---

## Installation

To install the library locally in editable development mode:

```bash
git clone https://github.com/Assistentus/magnus.git
cd magnus
pip install -e .


---

## Verification & Unit Tests

The mathematical soundness of the implementation is verified using strict algebraic invariants (Theorem 5 of the foundational paper). In a finitely presented group:
1.  The homological factor of the $c_1 = rr + frf + rff$ code must have a dimension strictly greater than or equal to $K$ (the number of generators).
2.  The homological factor of the sub-code $c_2 = rr + frf$ must be greater than or equal to the factor of $c_1$.

To run the algebraic verification suite:

```bash
python -m pytest tests/test_core.py -v -s
```

---

## Usage Example

```python
from magnus import TextPresentation, MagnusAlgebra, FRCodeRegistry, HomologySolver

# 1. Provide a text corpus
text = "The man saw a house. The house stood on a hill. The man walked to the house."

# 2. Build the homological presentation (e.g., K=15 generators)
# This automatically runs the Homological Feature Selection to extract the structural basis
pres = TextPresentation(text, k_vocab=15)

# 3. Initialize Magnus algebra up to degree 4
magnus = MagnusAlgebra(K=pres.k_vocab, degree=4)
r_generators = [magnus.expand_word(rel) for rel in pres.relations]

# 4. Build the boundary matrix for the H_3 homology invariant (rr + frf)
c_matrix = FRCodeRegistry.build_rr_frf(magnus, r_generators)

# 5. Evaluate the exact rank and quotient dimension over Z_p
solver = HomologySolver()
results = solver.evaluate(c_matrix, dim_f=magnus.dim)

print(f"Free space dimension: {results['dim_f']}")
print(f"Boundary matrix rank: {results['rank_c']}")
print(f"Homological factor:   {results['dim_factor']} (strictly >= K)")
```

---

## Note on Performance

This open-source package provides a pure Python implementation of the sparse Gaussian elimination solver. It is mathematically exact and suitable for small-to-medium datasets (up to ~100 relations) for research, verification, and educational purposes. Processing large, dense corpora generates heavy algebraic systems that may exceed Python's optimal memory and execution constraints.

---

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.
```
