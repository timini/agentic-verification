"""Pairwise coverage overlap (Jaccard) via a sparse incidence matrix, plus line multiplicity.

Overlap is a discovery signal only: tests that execute the same lines can still assert
different things. Callers must not turn a high score into deletion advice.
"""

from collections import Counter

import numpy as np
from scipy import sparse


def jaccard_pairs(lines_by_test: dict[str, set], threshold: float, min_union: int = 5) -> list[tuple[str, str, float, int]]:
    """All pairs with Jaccard >= threshold and |union| >= min_union. Empty sets never pair."""
    tests = sorted(t for t, v in lines_by_test.items() if v)
    if len(tests) < 2:
        return []
    vocab: dict = {}
    rows, cols = [], []
    for i, t in enumerate(tests):
        for ln in lines_by_test[t]:
            rows.append(i)
            cols.append(vocab.setdefault(ln, len(vocab)))
    m = sparse.csr_matrix((np.ones(len(rows), dtype=np.int32), (rows, cols)), shape=(len(tests), len(vocab)))
    inter = sparse.triu(m @ m.T, k=1).tocoo()
    size = np.asarray(m.sum(axis=1)).ravel()
    out = []
    for i, j, n in zip(inter.row, inter.col, inter.data):
        union = size[i] + size[j] - n
        if union >= min_union and n / union >= threshold:
            out.append((tests[i], tests[j], float(n / union), int(union)))
    return out


def multiplicity(lines_by_test: dict[str, set]) -> Counter:
    """Line -> number of distinct tests observed executing it."""
    c: Counter = Counter()
    for lines in lines_by_test.values():
        c.update(lines)
    return c
