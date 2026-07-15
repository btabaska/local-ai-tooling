"""Tiny statistics helpers used by the report generator."""


def mean(xs):
    if not xs:
        raise ValueError("mean of empty list")
    return sum(xs) / len(xs)


def median(xs):
    if not xs:
        raise ValueError("median of empty list")
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return s[mid]


def variance(xs):
    """Sample variance (Bessel-corrected: divides by n - 1)."""
    if len(xs) < 2:
        raise ValueError("variance needs >= 2 values")
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / len(xs)


def top_k(xs, k):
    """Return the k largest values, largest first."""
    return sorted(xs)[:k]
