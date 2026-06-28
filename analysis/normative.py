"""Normative statistics: metric direction, group stats, z-scores, percentiles.

All pseudo-normative — reference is built from Canada Basketball's own athletes
within each group, not an external population. Keep that explicit in the UI.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# --- Metric direction -------------------------------------------------------
HIGHER = "higher"   # higher is better
LOWER = "lower"     # lower is better
ZERO = "zero"       # closer to 0 is better (asymmetry)

_LOWER_HINTS = ("landing force", "contact time", "time to", "depth",
                "asymmetry duration")
_HIGHER_HINTS = ("height", "rsi", "power", "force", "impulse", "velocity",
                 "rfd", "stiffness", "speed", "momentum")


def metric_direction(metric: str) -> str:
    """Name-based default for whether higher / lower / closer-to-0 is better."""
    m = metric.lower()
    if "asym" in m:
        return ZERO
    for h in _LOWER_HINTS:
        if h in m:
            return LOWER
    for h in _HIGHER_HINTS:
        if h in m:
            return HIGHER
    return HIGHER


def z_band(z: float, direction: str) -> str:
    """Classify a z-score into go / maintain / backoff given metric direction.

    For HIGHER: high z = good. For LOWER: low z = good. For ZERO: magnitude.
    Returns one of 'go', 'maintain', 'backoff'.
    """
    if z is None or (isinstance(z, float) and np.isnan(z)):
        return "maintain"
    if direction == ZERO:
        az = abs(z)
        if az <= 0.5:
            return "go"
        if az <= 1.0:
            return "maintain"
        return "backoff"
    signed = z if direction == HIGHER else -z
    if signed >= 0.5:
        return "go"
    if signed >= -0.5:
        return "maintain"
    return "backoff"


def value_deficit(value, reference, direction: str = HIGHER) -> float:
    """How far `value` falls short of `reference`, as a positive %.

    Direction-aware: for HIGHER-better, being below the reference is the deficit;
    for LOWER-better, being above it is; for ZERO (asymmetry) the magnitude itself
    is the deficit. Negative result = a surplus (no deficit).
    """
    if value is None or pd.isna(value):
        return np.nan
    if direction == ZERO:
        return abs(float(value))
    if reference is None or pd.isna(reference) or reference == 0:
        return np.nan
    if direction == LOWER:
        return (float(value) - reference) / abs(reference) * 100.0
    return (reference - float(value)) / abs(reference) * 100.0


def deficit_band(deficit_pct) -> str:
    """Site-wide deficit colour bands:
    <1% surplus/par -> go (green) · 1–10% -> maintain (yellow) ·
    10–15% -> caution (orange) · 15%+ -> backoff (red).
    """
    if deficit_pct is None or pd.isna(deficit_pct):
        return "go"
    d = float(deficit_pct)
    if d < 1:
        return "go"
    if d < 10:
        return "maintain"
    if d < 15:
        return "caution"
    return "backoff"


# --- Percentiles ------------------------------------------------------------
def percentiles(values, qs=(25, 50, 75, 90)) -> dict[int, float]:
    """Percentiles via linear interpolation (numpy default)."""
    arr = np.asarray([v for v in values if pd.notna(v)], dtype=float)
    if arr.size == 0:
        return {q: np.nan for q in qs}
    return {q: float(np.percentile(arr, q)) for q in qs}


def percentile_of(value: float, values, direction: str = HIGHER) -> float:
    """Percentile rank (0-100) of `value` within `values`.

    Direction-aware: for LOWER-is-better metrics the rank is inverted so a high
    percentile always means 'good'. For ZERO, ranks by closeness to 0.
    """
    arr = np.asarray([v for v in values if pd.notna(v)], dtype=float)
    if arr.size == 0 or pd.isna(value):
        return np.nan
    if direction == ZERO:
        arr = -np.abs(arr)
        value = -abs(value)
    elif direction == LOWER:
        arr = -arr
        value = -value
    # fraction strictly below + half of ties => standard mid-rank percentile
    below = np.sum(arr < value)
    equal = np.sum(arr == value)
    return float((below + 0.5 * equal) / arr.size * 100.0)


def zscore(value: float, mean: float, sd: float) -> float:
    if pd.isna(value) or pd.isna(mean) or not sd or pd.isna(sd) or sd == 0:
        return np.nan
    return float((value - mean) / sd)


# --- Hawkin-style scaled score (modified z) ---------------------------------
def scaled_score(value: float, values, direction: str = HIGHER) -> float:
    """Map a value to 0-100 where 50 = group mean, 100 = best, 0 = worst.

    Direction-aware (Hawkin Dynamics "modified z-score" convention). Piecewise
    linear on each side of the mean so the mean always lands on 50.
    """
    arr = np.asarray([v for v in values if pd.notna(v)], dtype=float)
    if arr.size == 0 or pd.isna(value):
        return np.nan
    # 'goodness' axis: higher is always better after this transform
    if direction == LOWER:
        g, gv = -arr, -value
    elif direction == ZERO:
        g, gv = -np.abs(arr), -abs(value)
    else:
        g, gv = arr, value
    worst, best, mean = float(g.min()), float(g.max()), float(g.mean())
    if gv <= mean:
        denom = mean - worst
        s = 50.0 * (gv - worst) / denom if denom else 50.0
    else:
        denom = best - mean
        s = 50.0 + 50.0 * (gv - mean) / denom if denom else 50.0
    return float(min(100.0, max(0.0, s)))


def best_fit(dates, values) -> tuple[np.ndarray, np.ndarray] | None:
    """Linear best-fit line (Hawkin trend-report style) over a time series.

    Returns (x_dates, y_fit) or None if too few points.
    """
    d = pd.to_datetime(pd.Series(list(dates)))
    y = np.asarray(list(values), dtype=float)
    mask = ~np.isnan(y)
    if mask.sum() < 2:
        return None
    x = d.astype("int64").to_numpy()[mask] / 8.64e13  # ns -> days
    yv = y[mask]
    m, b = np.polyfit(x - x.min(), yv, 1)
    xf = np.array([x.min(), x.max()])
    yf = m * (xf - x.min()) + b
    return d[mask].iloc[[0, -1]].to_numpy(), yf


# --- Group aggregation ------------------------------------------------------
def group_stats(values) -> dict:
    """n, mean, sd, cv%, min, p25, median, p75, p90, max for one metric/group."""
    arr = np.asarray([v for v in values if pd.notna(v)], dtype=float)
    if arr.size == 0:
        return dict(n=0, mean=np.nan, sd=np.nan, cv=np.nan, min=np.nan,
                    p25=np.nan, median=np.nan, p75=np.nan, p90=np.nan, max=np.nan)
    mean = float(arr.mean())
    sd = float(arr.std(ddof=1)) if arr.size > 1 else 0.0
    pc = percentiles(arr)
    return dict(
        n=int(arr.size),
        mean=mean,
        sd=sd,
        cv=float(sd / mean * 100.0) if mean else np.nan,
        min=float(arr.min()),
        p25=pc[25],
        median=pc[50],
        p75=pc[75],
        p90=pc[90],
        max=float(arr.max()),
    )


def representative_values(
    df: pd.DataFrame, metric: str, how: str = "latest"
) -> pd.DataFrame:
    """One representative value per **athlete × group** for a single metric.

    Grouping by (athlete, group) — not athlete alone — is what makes FIBA age
    banding correct: an athlete who tested at 17 and again at 19 contributes one
    value to U18 and one to U20. For single-group modes (All athletes, position)
    each athlete still yields exactly one row.

    `how`: 'latest' | 'best' | 'mean'. 'best' is direction-aware.
    Returns columns: athlete, group, value, test_date, n_tests.
    """
    sub = df[df["metric"] == metric].dropna(subset=["value"]).copy()
    if sub.empty:
        return pd.DataFrame(columns=["athlete", "group", "value", "test_date", "n_tests"])
    sub["group"] = sub["group"].fillna("All Athletes")
    direction = metric_direction(metric)
    out = []
    for (athlete, grp), g in sub.groupby(["athlete", "group"]):
        n = len(g)
        if how == "mean":
            val, date = float(g["value"].mean()), g["test_date"].max()
        elif how == "best":
            if direction == LOWER:
                row = g.loc[g["value"].idxmin()]
            elif direction == ZERO:
                row = g.loc[g["value"].abs().idxmin()]
            else:
                row = g.loc[g["value"].idxmax()]
            val, date = float(row["value"]), row["test_date"]
        else:  # latest
            row = g.sort_values("test_date").iloc[-1]
            val, date = float(row["value"]), row["test_date"]
        out.append(dict(athlete=athlete, group=grp, value=val,
                        test_date=date, n_tests=n))
    return pd.DataFrame(out)


def normative_table(df: pd.DataFrame, metric: str, how: str = "latest") -> pd.DataFrame:
    """Per-group normative stats for a metric, one row per group."""
    rep = representative_values(df, metric, how)
    if rep.empty:
        return pd.DataFrame()
    rep["group"] = rep["group"].fillna("All Athletes")
    rows = []
    for grp, g in rep.groupby("group"):
        s = group_stats(g["value"])
        s = {"group": grp, **s}
        rows.append(s)
    cols = ["group", "n", "mean", "sd", "cv", "min", "p25", "median",
            "p75", "p90", "max"]
    return pd.DataFrame(rows)[cols].sort_values("group").reset_index(drop=True)
