"""Reusable UI atoms + chart builders shared across pages.

Keeps page modules declarative: they assemble these, the math stays in analysis/*.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analysis import normative as norm, athlete as ath
from . import theme as T


# ---------------------------------------------------------------------------
# Atoms
# ---------------------------------------------------------------------------
def fmt(v, n=1):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:,.{n}f}"


def tile(label, value, unit="", sub="", delta=None):
    """Metric tile. `delta` = dict(pct, sign) renders a Hawkin-style ▲/▼ change."""
    d = ""
    if delta:
        c = T.GO if delta["sign"] > 0 else (T.BACKOFF if delta["sign"] < 0 else T.INK_MUTED)
        arrow = "▲" if delta["sign"] > 0 else ("▼" if delta["sign"] < 0 else "▬")
        pct = delta.get("pct")
        ptxt = "—" if pct is None or (isinstance(pct, float) and np.isnan(pct)) else f"{abs(pct):.1f}%"
        lbl = delta.get("label", "vs prev")
        d = (f'<span class="cb-delta" style="color:{c}">{arrow} {ptxt}'
             f'<span style="color:{T.INK_FAINT}"> {lbl}</span></span>')
    st.markdown(
        f"""<div class="cb-tile">
        <div class="cb-label">{label}</div>
        <div class="cb-metric">{value}<span class="u">{unit}</span></div>
        <div class="cb-sub">{sub} {d}</div></div>""",
        unsafe_allow_html=True,
    )


def chip(band, text):
    c = T.BAND_COLORS.get(band, T.INK_MUTED)
    return (f'<span class="cb-chip"><span class="cb-dot" '
            f'style="background:{c}"></span>{text}</span>')


def section_label(icon_name, text):
    st.markdown(
        f'<div class="cb-head" style="margin:10px 0 4px">{T.icon(icon_name, 16, T.RED)}'
        f'<span class="cb-label">{text}</span></div>',
        unsafe_allow_html=True,
    )


def legend_bands():
    st.markdown(
        f'<span class="cb-legend">{chip("go","≤1% / above")} &nbsp; '
        f'{chip("maintain","1–10% deficit")} &nbsp; {chip("caution","10–15% deficit")} &nbsp; '
        f'{chip("backoff","15%+ deficit")}</span>',
        unsafe_allow_html=True,
    )


def unit_for(tdf, metric):
    u = tdf[tdf["metric"] == metric]["unit"].dropna()
    return u.iloc[0] if not u.empty else ""


_DIR_LABEL = {"higher": "Higher is better", "lower": "Lower is better",
              "zero": "Closer to 0 is better"}

# Preferred headline metric per test, in priority order (first match wins).
_DEFAULT_METRIC_KW = ("jump height", "rebound rsi", "rsi", "peak power", "impulse")


def smart_default_metric(metrics):
    """A sensible primary metric for a test: jump height / rebound RSI / etc."""
    nonasym = [m for m in metrics if norm.metric_direction(m) != norm.ZERO] or metrics
    for kw in _DEFAULT_METRIC_KW:
        m = next((x for x in nonasym if kw in x.lower()), None)
        if m:
            return m
    return nonasym[0] if nonasym else metrics[0]


def test_picker(df_all, test_types, default, key="active_test", label="Test"):
    """Test-type selector (shared across pages). Returns (test_type, metrics)."""
    if not test_types:
        return None, []
    cur = st.session_state.get(key)
    val = cur if cur in test_types else (default if default in test_types else test_types[0])
    if len(test_types) > 1:
        test_type = st.selectbox(label, test_types, index=test_types.index(val), key=key)
    else:
        test_type = test_types[0]
    metrics = sorted(df_all[df_all["test_type"] == test_type]["metric"].dropna().unique())
    return test_type, metrics


def group_picker(ctx, key="group_basis", label="Group by"):
    """Grouping-basis selector (shared across pages). Returns mode_key.

    Age bands are offered on every page wherever data supports them.
    """
    bases = ["All athletes"]
    if ctx.has_group:
        bases.append("Position")
    if ctx.has_birthyear:
        bases.append("Age band (FIBA)")
    default = {"age_band": "Age band (FIBA)", "detected": "Position",
               "all": "All athletes"}.get(ctx.mode_key, "All athletes")
    cur = st.session_state.get(key)
    val = cur if cur in bases else (default if default in bases else bases[0])
    basis = st.selectbox(label, bases, index=bases.index(val), key=key) \
        if len(bases) > 1 else bases[0]
    return ("age_band" if basis.startswith("Age")
            else "detected" if basis == "Position" else "all")


def scoped_tdf(ctx, test_type, mode):
    """Frame for `test_type`, grouped by `mode` (regrouped from the ungrouped base)."""
    from analysis import grouping
    sub = ctx.base[ctx.base["test_type"] == test_type]
    return grouping.apply_grouping(sub, mode)


def _guard_key(key, options):
    """Drop a persisted selectbox value that isn't valid for the current options
    (prevents a Streamlit error when the test type changes the metric list)."""
    if key in st.session_state and st.session_state[key] not in options:
        del st.session_state[key]


def metric_picker(tdf, metrics, key, label="Metric", default=None):
    """Inline metric selector. Returns (metric, unit, direction, dir_label)."""
    if not metrics:
        return None, "", "higher", ""
    _guard_key(key, metrics)
    if default is None or default not in metrics:
        default = smart_default_metric(metrics)
    metric = st.selectbox(label, metrics, index=metrics.index(default), key=key)
    direction = norm.metric_direction(metric)
    return metric, unit_for(tdf, metric), direction, _DIR_LABEL[direction]


# Default ordering for the front-facing metric cards (most relevant first).
_CARD_PRIORITY = ("jump height", "rebound rsi", "rsi", "peak power",
                  "concentric impulse", "eccentric braking", "mean force",
                  "p1 concentric", "impulse", "bw")


def ordered_perf_metrics(metrics):
    """Non-asymmetry metrics, ordered so the default cards show the key ones."""
    perf = [m for m in metrics if norm.metric_direction(m) != norm.ZERO]

    def rank(m):
        ml = m.lower()
        return next((i for i, kw in enumerate(_CARD_PRIORITY) if kw in ml),
                    len(_CARD_PRIORITY))
    return sorted(perf, key=rank) or list(metrics)


def metric_card(tdf, metrics, athlete, key, default):
    """A selectable metric card: dropdown + latest value + 30-day-avg trend under it."""
    from analysis import athlete as A
    if not metrics:
        return None
    _guard_key(key, metrics)
    if default not in metrics:
        default = metrics[0]
    metric = st.selectbox("metric", metrics, index=metrics.index(default), key=key,
                          label_visibility="collapsed")
    latest = A._athlete_value(tdf, athlete, metric, "latest")
    unit = unit_for(tdf, metric)
    dlt = A.delta_vs_recent(tdf, athlete, metric)
    trend = ""
    if dlt:
        deficit = norm.value_deficit(dlt["last"], dlt["recent"], norm.metric_direction(metric))
        c = T.BAND_COLORS[norm.deficit_band(deficit)]
        arrow = "▲" if dlt["sign"] > 0 else ("▼" if dlt["sign"] < 0 else "▬")
        pct = dlt.get("pct")
        ptxt = "—" if pct is None or (isinstance(pct, float) and np.isnan(pct)) else f"{abs(pct):.1f}%"
        trend = (f'<div class="cb-sub" style="margin-top:8px;text-align:center">'
                 f'<span class="cb-delta" style="color:{c}">{arrow} {ptxt}'
                 f'<span style="color:{T.INK_FAINT}"> vs 30d avg</span></span></div>')
    st.markdown(
        f'<div style="border-top:1px solid {T.RULE};padding-top:12px;margin-top:2px;'
        f'text-align:center">'
        f'<div class="cb-metric" style="font-size:38px">{fmt(latest)}'
        f'<span class="u">{unit}</span></div>{trend}</div>', unsafe_allow_html=True)
    return metric


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def trend_chart(tdf, athletes, metric, unit, group_mean=None, group_sd=None,
                height=340, band_label="group"):
    """Time-series for one or more athletes with optional ±1 SD norm band + best-fit."""
    if isinstance(athletes, str):
        athletes = [athletes]
    fig = go.Figure()
    if group_mean is not None and not np.isnan(group_mean):
        all_dates = tdf[tdf["metric"] == metric]["test_date"]
        xb = [all_dates.min(), all_dates.max()]
        if group_sd is not None and not np.isnan(group_sd):
            fig.add_scatter(x=xb + xb[::-1],
                            y=[group_mean + group_sd, group_mean + group_sd,
                               group_mean - group_sd, group_mean - group_sd],
                            fill="toself", fillcolor="rgba(200,16,46,0.10)",
                            line=dict(width=0), hoverinfo="skip",
                            name=f"{band_label} ±1 SD")
        fig.add_hline(y=group_mean, line=dict(color=T.INK_MUTED, dash="dash", width=1),
                      annotation_text=f"{band_label} mean", annotation_position="top left",
                      annotation_font_color=T.INK_MUTED)
    palette = [T.RED, "#5b9bd5", "#e0e0e0", "#f0a500"]
    for i, a in enumerate(athletes):
        ts = ath.athlete_trend(tdf, a, metric)
        if ts.empty:
            continue
        col = palette[i % len(palette)]
        if len(athletes) == 1:
            bf = norm.best_fit(ts["test_date"], ts["value"])
            if bf is not None:
                fig.add_scatter(x=bf[0], y=bf[1], mode="lines", name="trend",
                                line=dict(color=T.INK_FAINT, dash="dot", width=1.5),
                                hoverinfo="skip")
        fig.add_scatter(x=ts["test_date"], y=ts["value"], mode="lines+markers",
                        line=dict(color=col, width=2), marker=dict(color=col, size=7),
                        name=a,
                        hovertemplate="%{x|%b %d, %Y}<br>%{y:.1f} " + unit + "<extra></extra>")
    fig.update_layout(**T.plotly_layout(height=height,
                      yaxis_title=f"{metric} [{unit}]" if unit else metric))
    return fig


def radar_chart(tdf, athletes, metrics, rep_how, height=420):
    """Hawkin-style scaled-0–100 profile radar for one or more athletes vs group (50)."""
    if isinstance(athletes, str):
        athletes = [athletes]
    fig = go.Figure()
    palette = [T.RED, "#5b9bd5", "#e0e0e0"]
    axis = None
    for i, a in enumerate(athletes):
        prof = ath.profile_scores(tdf, a, metrics, rep_how)
        if len(prof) < 3:
            continue
        if axis is None:
            axis = list(prof["metric"]) + [prof["metric"].iloc[0]]
            fig.add_scatterpolar(r=[50] * len(axis), theta=axis, mode="lines",
                                 line=dict(color=T.INK_FAINT, width=1, dash="dot"),
                                 name="group mean", hoverinfo="skip")
        vals = list(prof["score"]) + [prof["score"].iloc[0]]
        col = palette[i % len(palette)]
        fig.add_scatterpolar(
            r=vals, theta=list(prof["metric"]) + [prof["metric"].iloc[0]],
            fill="toself" if len(athletes) == 1 else None,
            fillcolor="rgba(200,16,46,0.20)", line=dict(color=col, width=2), name=a,
            hovertemplate="%{theta}<br>%{r:.0f}/100<extra></extra>")
    fig.update_layout(**T.plotly_layout(height=height, showlegend=True,
        polar=dict(bgcolor="rgba(0,0,0,0)",
                   radialaxis=dict(range=[0, 100], gridcolor=T.RULE,
                                   tickfont=dict(color=T.INK_FAINT, size=9), showline=False),
                   angularaxis=dict(gridcolor=T.RULE,
                                    tickfont=dict(color=T.INK_MUTED, size=10)))))
    return fig, (axis is not None)


def short_metric(m):
    """Compact axis label: drop the unit/parenthetical so radar labels fit."""
    return str(m).split("(")[0].strip()


def radar_from_frame(prof, series, height=440, radial_range=(0, 100), hover_suffix="/100"):
    """Radar from a frame with a `metric` column + one column per series.

    `series`: list of (column, label, line_color, fill_color_or_None).
    `radial_range`: axis range — e.g. (50, 150) centres a 100 baseline so the
    reference reads as an even mid-radar circle and deviations push out/in.
    Rows with NaN in any plotted series are dropped to keep a closed polygon.
    """
    cols = [s[0] for s in series]
    prof = prof.dropna(subset=cols)
    if len(prof) < 3:
        return go.Figure(), False
    labels = [short_metric(m) for m in prof["metric"]]
    theta = labels + [labels[0]]
    fig = go.Figure()
    for col, label, line_color, fill_color in series:
        r = list(prof[col]) + [prof[col].iloc[0]]
        fig.add_scatterpolar(
            r=r, theta=theta, name=label,
            fill="toself" if fill_color else None, fillcolor=fill_color,
            line=dict(color=line_color, width=2 if fill_color else 1.3,
                      dash=None if fill_color else "dot"),
            hovertemplate="%{theta}<br>%{r:.0f}" + hover_suffix + "<extra>" + label + "</extra>")
    fig.update_layout(**T.plotly_layout(
        height=height, showlegend=True, margin=dict(l=70, r=70, t=24, b=64),
        legend=dict(orientation="h", yanchor="top", y=-0.1, x=0.5, xanchor="center",
                    font=dict(color=T.INK_MUTED, size=10)),
        polar=dict(domain=dict(y=[0.06, 1]), bgcolor="rgba(0,0,0,0)",
                   radialaxis=dict(range=list(radial_range), gridcolor=T.RULE,
                                   tickfont=dict(color=T.INK_FAINT, size=9), showline=False),
                   angularaxis=dict(gridcolor=T.RULE,
                                    tickfont=dict(color=T.INK_MUTED, size=10)))))
    return fig, True


def ranking_chart(rep, metric, unit, direction, height=None):
    """Horizontal athlete ranking coloured by deficit-from-mean with ±1 SD context."""
    stats = norm.group_stats(rep["value"])
    rep = rep.copy()
    rep["band"] = rep["value"].apply(
        lambda v: norm.deficit_band(norm.value_deficit(v, stats["mean"], direction)))
    rep = rep.sort_values("value", ascending=(direction != "lower"))
    fig = go.Figure()
    if not np.isnan(stats["sd"]):
        fig.add_vrect(x0=stats["mean"] - stats["sd"], x1=stats["mean"] + stats["sd"],
                      fillcolor="rgba(255,255,255,0.04)", line_width=0, layer="below",
                      annotation_text="±1 SD", annotation_position="top left",
                      annotation_font_color=T.INK_FAINT)
    fig.add_bar(y=rep["athlete"], x=rep["value"], orientation="h",
                marker_color=[T.BAND_COLORS[b] for b in rep["band"]], marker_line_width=0,
                hovertemplate="%{y}<br>%{x:.1f} " + unit + "<extra></extra>")
    fig.add_vline(x=stats["mean"], line=dict(color=T.INK_MUTED, dash="dash", width=1),
                  annotation_text="group mean", annotation_font_color=T.INK_MUTED)
    fig.update_layout(**T.plotly_layout(height=height or max(300, 30 * len(rep)),
                      xaxis_title=f"{metric} [{unit}]" if unit else metric))
    return fig


def asym_bars(fm, threshold, cap=28, height=None):
    """Bilateral diverging asymmetry bars (L negative / R positive), deficit-banded."""
    plot = fm.sort_values("magnitude", ascending=False).head(cap).sort_values("value")
    colors = [T.BAND_COLORS[norm.deficit_band(m)] for m in plot["magnitude"]]
    fig = go.Figure()
    fig.add_vrect(x0=-threshold, x1=threshold, fillcolor="rgba(74,222,128,0.07)",
                  line_width=0, layer="below")
    fig.add_bar(y=plot["athlete"], x=plot["value"], orientation="h",
                marker_color=colors, marker_line_width=0,
                hovertemplate="%{y}<br>%{x:.1f}% <extra></extra>")
    fig.add_vline(x=0, line=dict(color=T.RULE, width=1))
    for xt in (-threshold, threshold):
        fig.add_vline(x=xt, line=dict(color=T.BACKOFF, dash="dot", width=1))
    fig.update_layout(**T.plotly_layout(height=height or max(320, 24 * len(plot)),
                      xaxis_title="◄ Left dominant      asymmetry %      Right dominant ►"))
    return fig, len(plot)


def show_chart(fig):
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
