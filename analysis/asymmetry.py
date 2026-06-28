"""Left:Right asymmetry flagging.

Asymmetry metrics are stored signed (R = +, L = -, see vald.schema). Thresholds
use the magnitude; the sign only tells you the dominant side.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import normative as norm

DEFAULT_THRESHOLD = 10.0  # percent


def asymmetry_metrics(df: pd.DataFrame) -> list[str]:
    """Metrics whose direction is 'closer-to-0' (i.e. asymmetry metrics)."""
    metrics = df["metric"].dropna().unique()
    return sorted(m for m in metrics if norm.metric_direction(m) == norm.ZERO)


def flag_asymmetries(
    df: pd.DataFrame, threshold: float = DEFAULT_THRESHOLD, how: str = "latest"
) -> pd.DataFrame:
    """One row per athlete x asymmetry-metric, flagged where |value| > threshold.

    Columns: athlete, group, metric, value (signed), magnitude, side, flagged.
    """
    rows = []
    for metric in asymmetry_metrics(df):
        rep = norm.representative_values(df, metric, how)
        if rep.empty:
            continue
        for _, r in rep.iterrows():
            val = r["value"]
            mag = abs(val)
            side = "R" if val > 0 else ("L" if val < 0 else "—")
            rows.append(dict(
                athlete=r["athlete"],
                group=r["group"] if pd.notna(r["group"]) else "All Athletes",
                metric=metric,
                value=val,
                magnitude=mag,
                side=side,
                flagged=bool(mag > threshold),
            ))
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["flagged", "magnitude"], ascending=[False, False]).reset_index(drop=True)


def recent_asymmetry_flags(
    df: pd.DataFrame,
    abs_threshold: float = 15.0,
    change_threshold: float = 10.0,
    recent_days: int = 30,
) -> pd.DataFrame:
    """Latest asymmetry vs the athlete's 30-day average, one row per athlete x metric.

    An athlete is flagged on a metric when the latest test's asymmetry magnitude
    is over `abs_threshold` (%), OR it has moved at least `change_threshold`
    percentage points from their `recent_days` average. The average is the prior
    `recent_days` of tests *before* the latest one, so today's test is compared
    against their established baseline rather than against itself.

    Columns: athlete, group, metric, value (signed latest), magnitude, side,
    avg30 (signed 30-day mean), change (|latest - avg30|, points), over_abs,
    over_change, flagged, reason. Sorted flagged-first, largest magnitude first.
    """
    from . import athlete as ath

    rows = []
    for metric in asymmetry_metrics(df):
        sub = df[df["metric"] == metric]
        for a in sub["athlete"].dropna().unique():
            ts = (sub[sub["athlete"] == a].dropna(subset=["value", "test_date"])
                  .sort_values("test_date"))
            if ts.empty:
                continue
            latest = float(ts["value"].iloc[-1])
            latest_date = ts["test_date"].iloc[-1]
            cutoff = latest_date.normalize() - pd.Timedelta(days=recent_days)
            prior = ts[(ts["test_date"] >= cutoff) & (ts["test_date"] < latest_date)]
            avg30 = float(prior["value"].mean()) if not prior.empty else np.nan
            mag = abs(latest)
            change = abs(latest - avg30) if pd.notna(avg30) else np.nan
            over_abs = bool(mag > abs_threshold)
            over_change = bool(pd.notna(change) and change >= change_threshold)
            reasons = []
            if over_abs:
                reasons.append(f"over {abs_threshold:.0f}%")
            if over_change:
                reasons.append(f"{change:.1f}-pt shift vs 30d avg")
            rows.append(dict(
                athlete=a,
                group=ath.primary_group(df, a),
                metric=metric,
                value=float(latest),
                magnitude=float(mag),
                side="R" if latest > 0 else ("L" if latest < 0 else "—"),
                avg30=float(avg30) if pd.notna(avg30) else np.nan,
                change=float(change) if pd.notna(change) else np.nan,
                over_abs=over_abs,
                over_change=over_change,
                flagged=bool(over_abs or over_change),
                reason=" · ".join(reasons),
            ))
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["flagged", "magnitude"],
                           ascending=[False, False]).reset_index(drop=True)
