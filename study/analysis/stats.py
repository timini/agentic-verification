"""Interval estimates named in the pre-registration."""

import math
import random
from typing import Callable, Sequence, TypeVar

T = TypeVar("T")
RESAMPLES = 10_000


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def cluster_bootstrap(
    clusters: Sequence[T], statistic: Callable[[list[T]], float], seed: int = 20261015,
    resamples: int = RESAMPLES,
) -> tuple[float, float]:
    """Percentile 95% interval, resampling whole clusters (projects) with replacement."""
    if not clusters:
        return (math.nan, math.nan)
    rng = random.Random(seed)
    vals = []
    for _ in range(resamples):
        sample = [clusters[rng.randrange(len(clusters))] for _ in clusters]
        v = statistic(sample)
        if not math.isnan(v):
            vals.append(v)
    if not vals:
        return (math.nan, math.nan)
    vals.sort()
    return (vals[int(0.025 * (len(vals) - 1))], vals[int(0.975 * (len(vals) - 1))])


def ratio(num: float, den: float) -> float:
    return num / den if den else math.nan
