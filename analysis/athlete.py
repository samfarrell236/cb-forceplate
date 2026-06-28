"""Per-athlete views: trend over time, and latest-vs-group-norm across metrics."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import normative as norm


def athlete_trend(df: pd.DataFrame, athlete: str, metric: str) -> pd.DataFrame:
    """Time-series for one athlete/metric: test_date, value (sorted)."""
    sub = df[(df["athlete"] == athlete) & (df["metric"] == metric)]
    sub = sub.dropna(subset=["value"]).sort_values("test_date")
    return sub[["test_date", "value", "unit"]].reset_index(drop=True)


def _peers(rep, grp):
    """Peer rows for a comparison group. 'All Athletes' = the whole cohort."""
    return rep if grp == "All Athletes" else rep[rep["group"] == grp]


def athlete_headline(
    df: pd.DataFrame, athlete: str, metric: str, how: str = "latest", ref_group=None
) -> dict:
    """Headline stats for an athlete on a metric vs a comparison group.

    `ref_group` selects which group to benchmark against (e.g. 'U18'); defaults
    to the athlete's own most-recent band.
    """
    rep = norm.representative_values(df, metric, how)
    if rep.empty or athlete not in set(rep["athlete"]):
        return {}
    rep["group"] = rep["group"].fillna("All Athletes")
    mine = rep[rep["athlete"] == athlete]
    me = mine.loc[mine["test_date"].idxmax()]          # athlete's most-recent value
    grp = ref_group or primary_group(df, athlete)
    peers = _peers(rep, grp)
    stats = norm.group_stats(peers["value"])
    direction = norm.metric_direction(metric)
    z = norm.zscore(me["value"], stats["mean"], stats["sd"])
    pct = norm.percentile_of(me["value"], peers["value"], direction)
    return dict(
        athlete=athlete,
        group=grp,
        value=float(me["value"]),
        unit=_unit_for(df, metric),
        n_tests=int(me["n_tests"]),
        group_n=stats["n"],
        group_mean=stats["mean"],
        group_sd=stats["sd"],
        z=z,
        percentile=pct,
        band=norm.deficit_band(norm.value_deficit(me["value"], stats["mean"], direction)),
        direction=direction,
    )


def latest_vs_norm(df: pd.DataFrame, athlete: str, how: str = "latest",
                   ref_group=None) -> pd.DataFrame:
    """Every metric for an athlete: their value vs group mean, with z + band.

    One row per metric. Sorted with asymmetry metrics last.
    """
    metrics = sorted(df[df["athlete"] == athlete]["metric"].dropna().unique())
    rows = []
    for metric in metrics:
        h = athlete_headline(df, athlete, metric, how, ref_group)
        if not h:
            continue
        rows.append(dict(
            metric=metric,
            value=h["value"],
            unit=h["unit"],
            group_mean=h["group_mean"],
            z=h["z"],
            percentile=h["percentile"],
            band=h["band"],
            direction=h["direction"],
        ))
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["_asym"] = out["direction"].eq(norm.ZERO).astype(int)
    return out.sort_values(["_asym", "metric"]).drop(columns="_asym").reset_index(drop=True)


def delta_vs_previous(df: pd.DataFrame, athlete: str, metric: str) -> dict:
    """Change in the latest test vs the previous one (Hawkin/VALD change view).

    Returns abs delta, % change, and sign (+1 improving / -1 declining / 0),
    interpreted by metric direction so 'improving' always means 'better'.
    """
    ts = athlete_trend(df, athlete, metric)
    if len(ts) < 2:
        return {}
    last, prev = float(ts["value"].iloc[-1]), float(ts["value"].iloc[-2])
    delta = last - prev
    pct = (delta / prev * 100.0) if prev else np.nan
    direction = norm.metric_direction(metric)
    if direction == norm.LOWER:
        better = delta < 0
    elif direction == norm.ZERO:
        better = abs(last) < abs(prev)
    else:
        better = delta > 0
    sign = 0 if delta == 0 else (1 if better else -1)
    return dict(delta=delta, pct=pct, sign=sign, last=last, prev=prev)


def delta_vs_recent(df, athlete, metric, recent_days=30):
    """Most-recent test vs the athlete's `recent_days` average (form trend).

    Returns abs delta, % change, and direction-aware sign (+1 better / -1 worse).
    """
    latest = _athlete_value(df, athlete, metric, "latest", recent_days)
    recent = _athlete_value(df, athlete, metric, "recent", recent_days)
    if pd.isna(latest) or pd.isna(recent):
        return {}
    delta = latest - recent
    pct = (delta / recent * 100.0) if recent else np.nan
    direction = norm.metric_direction(metric)
    if direction == norm.LOWER:
        better = delta < 0
    elif direction == norm.ZERO:
        better = abs(latest) < abs(recent)
    else:
        better = delta > 0
    sign = 0 if delta == 0 else (1 if better else -1)
    return dict(delta=delta, pct=pct, sign=sign, last=latest, recent=recent,
               label="vs 30d avg")


def profile_scores(df: pd.DataFrame, athlete: str, metrics: list[str],
                   how: str = "latest", ref_group=None) -> pd.DataFrame:
    """Scaled 0-100 score per metric for an athlete vs a comparison group.

    50 = the `ref_group` average (defaults to the athlete's own band).
    """
    grp = ref_group or primary_group(df, athlete)
    rows = []
    for metric in metrics:
        rep = norm.representative_values(df, metric, how)
        if rep.empty or athlete not in set(rep["athlete"]):
            continue
        rep["group"] = rep["group"].fillna("All Athletes")
        mine = rep[rep["athlete"] == athlete]
        me = float(mine.loc[mine["test_date"].idxmax(), "value"])
        peers = _peers(rep, grp)["value"]
        direction = norm.metric_direction(metric)
        rows.append(dict(
            metric=metric,
            score=norm.scaled_score(me, peers, direction),
            value=me,
            deficit=norm.value_deficit(me, peers.mean(), direction),
        ))
    return pd.DataFrame(rows)


def primary_group(df: pd.DataFrame, athlete: str):
    """The athlete's group from their most-recent test (their 'current' band)."""
    sub = df[(df["athlete"] == athlete)].dropna(subset=["test_date"])
    if sub.empty:
        g = df.loc[df["athlete"] == athlete, "group"].dropna()
        return g.iloc[0] if not g.empty else "All Athletes"
    grp = sub.sort_values("test_date").iloc[-1]["group"]
    return grp if pd.notna(grp) else "All Athletes"


def _athlete_value(df, athlete, metric, basis, recent_days=30):
    """One athlete's value for a metric under a time basis.

    basis: 'latest' (last test) | 'recent' (mean of last `recent_days`) |
    'alltime' (mean of full history). Window is relative to the athlete's most
    recent test, so it's robust to stale calendars.
    """
    sub = (df[(df["athlete"] == athlete) & (df["metric"] == metric)]
           .dropna(subset=["value", "test_date"]).sort_values("test_date"))
    if sub.empty:
        return np.nan
    if basis == "latest":
        return float(sub["value"].iloc[-1])
    if basis == "alltime":
        return float(sub["value"].mean())
    cutoff = sub["test_date"].max().normalize() - pd.Timedelta(days=recent_days)
    recent = sub[sub["test_date"] >= cutoff]
    return float(recent["value"].mean()) if not recent.empty else np.nan


def comparison_profile(df, athlete, metrics, mode, recent_days=30):
    """Self-comparison radar: current as a % of the athlete's OWN baseline.

    The baseline (ref) is 100 for every metric — an 'even' circle centred on the
    radar — and the current series shows each metric as a % of that baseline, so
    improvements push the shape out and declines pull it in.

    mode 'recent_alltime' -> baseline = all-time avg, current = recent (30d) avg.
    mode 'latest_recent'  -> baseline = recent (30d) avg, current = latest test.
    """
    base_basis, cur_basis = (("alltime", "recent") if mode == "recent_alltime"
                             else ("recent", "latest"))
    rows = []
    for metric in metrics:
        base = _athlete_value(df, athlete, metric, base_basis, recent_days)
        cur = _athlete_value(df, athlete, metric, cur_basis, recent_days)
        if pd.isna(base) or pd.isna(cur) or base == 0:
            continue
        rows.append(dict(metric=metric, ref=100.0, cur=float(cur) / base * 100.0,
                         base_val=float(base), cur_val=float(cur)))
    return pd.DataFrame(rows)


def recently_tested(df: pd.DataFrame, n: int = 20) -> list[str]:
    """Athletes ordered by their most recent test date (most recent first)."""
    last = df.groupby("athlete")["test_date"].max().sort_values(ascending=False)
    return list(last.index[:n])


def squad_matrix(df: pd.DataFrame, metrics: list[str], rep_how: str = "latest",
                 athletes: list[str] | None = None) -> pd.DataFrame:
    """Athletes × metrics matrix of scaled 0-100 scores (the 'team report card').

    Each column is scaled within its own group context (50 = group mean). Rows
    are athletes; missing metrics are NaN. Restrict to `athletes` if given.
    """
    cols = {}
    for metric in metrics:
        rep = norm.representative_values(df, metric, rep_how)
        if rep.empty:
            continue
        rep["group"] = rep["group"].fillna("All Athletes")
        scores = {}
        for grp, g in rep.groupby("group"):
            for _, r in g.iterrows():
                scores[r["athlete"]] = norm.scaled_score(
                    r["value"], g["value"], norm.metric_direction(metric))
        cols[metric] = scores
    mat = pd.DataFrame(cols)
    if athletes is not None:
        mat = mat.reindex(athletes)
    return mat


def _unit_for(df: pd.DataFrame, metric: str) -> str:
    u = df[df["metric"] == metric]["unit"].dropna()
    return u.iloc[0] if not u.empty else ""
