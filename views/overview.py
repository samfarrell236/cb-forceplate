"""Overview page — squad-wide situational awareness at a glance."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analysis import normative as norm, athlete as ath, asymmetry as asym, grouping
from ui import components as C, theme as T


def render(ctx):
    rep_how = ctx.rep_how

    # --- page controls: test + age group + window (no metric at the top) ---
    cc = st.columns([1.5, 1.8, 3])
    with cc[0]:
        test_type, metrics = C.test_picker(ctx.base, ctx.test_types, ctx.default_test)
    gmode = ("age_band" if ctx.has_birthyear
             else "detected" if ctx.has_group else "all")
    banded = C.scoped_tdf(ctx, test_type, gmode)
    present = [g for g in banded["group"].unique()
               if g != grouping.UNKNOWN_BAND and isinstance(g, str) and g != "All Athletes"]
    bands = grouping.sort_bands(present) if gmode == "age_band" else sorted(present)
    cohort_opts = ["All athletes"] + bands
    with cc[1]:
        C._guard_key("ov_cohort", cohort_opts)
        cohort = st.selectbox("Age group" if gmode == "age_band" else "Group",
                              cohort_opts, key="ov_cohort")
    tdf = banded if cohort == "All athletes" else banded[banded["group"] == cohort]
    with cc[2]:
        win = st.radio("Window", ["Last 7 days", "Last 30 days", "Last 90 days", "All time"],
                       index=0, horizontal=True, key="ov_window")
    max_date = tdf["test_date"].max()

    # the 3 table metrics are configured in Settings (set_ov_m1/2/3); fall back to
    # this test's defaults when unset or not valid for the current test.
    ord_perf = C.ordered_perf_metrics(metrics)
    defaults = [ord_perf[i] if i < len(ord_perf) else
                (ord_perf[0] if ord_perf else None) for i in range(3)]

    def _table_metric(setkey, idx):
        v = st.session_state.get(setkey)
        return v if v in metrics else defaults[idx]

    m1 = _table_metric("set_ov_m1", 0)
    m2 = _table_metric("set_ov_m2", 1)
    m3 = _table_metric("set_ov_m3", 2)
    table_metrics = list(dict.fromkeys([m for m in (m1, m2, m3) if m]))
    metric = m1
    unit = C.unit_for(tdf, metric) if metric else ""
    direction = norm.metric_direction(metric) if metric else "higher"

    C.section_label("chart", f"Most recent tests · {test_type}")
    if ctx.banner:
        st.caption(ctx.banner)
    days = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90}.get(win)
    if days and pd.notna(max_date):
        since = max_date.normalize() - pd.Timedelta(days=days)
        recent = tdf[tdf["test_date"] >= since]
    else:
        since, recent = None, tdf

    rep = norm.representative_values(tdf, metric, rep_how)
    aflags = asym.recent_asymmetry_flags(tdf)
    recent_ath = set(recent["athlete"].unique())
    flagged_ath = set(aflags[aflags["flagged"]]["athlete"]) if not aflags.empty else set()
    n_flag_recent = len(recent_ath & flagged_ath)
    rsess = recent[["athlete", "test_date"]].drop_duplicates()
    rvals = recent[recent["metric"] == metric]["value"]

    # --- KPI row (scoped to the window) -------------------------------------
    k = st.columns(5)
    with k[0]:
        C.tile("Athletes", str(len(recent_ath)), "", "tested in window")
    with k[1]:
        C.tile("Tests", f"{rsess.shape[0]:,}", "", "sessions in window")
    with k[2]:
        C.tile("Latest", max_date.strftime("%b %d") if pd.notna(max_date) else "—",
               "", max_date.strftime("%Y") if pd.notna(max_date) else "")
    with k[3]:
        C.tile(f"{_short(metric)}", C.fmt(rvals.mean()) if not rvals.empty else "—",
               unit, "window avg")
    with k[4]:
        C.tile("Asym flags", str(n_flag_recent), "", "tested recently")
    st.markdown(C.chip("backoff" if n_flag_recent else "go",
                f"{n_flag_recent} recently-tested athlete(s) with an asymmetry flag"),
                unsafe_allow_html=True)

    # --- latest tests (3 metric columns set in Settings) --------------------
    C.section_label("trend", "Latest tests")
    rec = recent.copy()
    rec["group"] = rec["group"].fillna("All Athletes")
    piv = (rec[rec["metric"].isin(table_metrics)]
           .pivot_table(index=["athlete", "test_date", "group"], columns="metric",
                        values="value", aggfunc="first")
           .reset_index().sort_values("test_date", ascending=False).head(40))
    if piv.empty:
        st.info("No tests in this window.")
    else:
        present_metrics = [m for m in table_metrics if m in piv.columns]
        # each athlete's recent (30-day) average per metric, to mark each cell
        recents = {(a, m): ath._athlete_value(tdf, a, m, "recent", 30)
                   for a in piv["athlete"].unique() for m in present_metrics}

        disp = pd.DataFrame({
            "Date": piv["test_date"].dt.strftime("%b %d · %H:%M").values,
            "Athlete": piv["athlete"].values, "Group": piv["group"].values})
        bands = {}
        for m in present_metrics:
            short, d, cells, brow = _short(m), norm.metric_direction(m), [], []
            for _, r in piv.iterrows():
                v, recv = r[m], recents.get((r["athlete"], m))
                if pd.isna(v):
                    cells.append("—"); brow.append(None); continue
                arrow = ""
                if pd.notna(recv) and recv and abs(v - recv) > 1e-9:
                    arrow = "▲" if v > recv else "▼"
                band = norm.deficit_band(norm.value_deficit(v, recv, d))
                cells.append(f"{v:.1f} {arrow}".strip()); brow.append(band)
            disp[short] = cells
            bands[short] = brow

        def _style(_df):
            out = pd.DataFrame("", index=_df.index, columns=_df.columns)
            for short, brow in bands.items():
                out[short] = [f"text-align:right;color:"
                              f"{T.BAND_COLORS.get(b, T.INK)}" for b in brow]
            return out

        # click any row to open that athlete's profile
        event = st.dataframe(
            disp.style.apply(_style, axis=None),
            width="stretch", hide_index=True,
            height=min(300, 40 + 30 * len(disp)),
            on_select="rerun", selection_mode="single-row",
            key="ov_latest_table")
        rows = event.selection.rows if event and event.selection else []
        if rows:
            st.session_state["ind_pick"] = disp["Athlete"].iloc[rows[0]]
            st.session_state["page"] = "Individual"
            # clear the selection so returning to Overview doesn't re-open it
            st.session_state.pop("ov_latest_table", None)
            st.rerun()
        st.caption(f"{len(piv)} session(s) · newest first · ▲/▼ = this test vs the "
                   "athlete's 30-day average (green = better) · click a row to "
                   "open that athlete's profile.")

    # --- Asymmetry flags ----------------------------------------------------
    C.section_label("alert", "Asymmetry flags")
    flagged = aflags[aflags["flagged"]] if not aflags.empty else aflags
    if flagged is None or flagged.empty:
        st.markdown(C.chip("go", "No asymmetry flags — every athlete within range."),
                    unsafe_allow_html=True)
    else:
        af = pd.DataFrame({
            "Athlete": flagged["athlete"].values,
            "Group": flagged["group"].values,
            "Metric": [_short(m) for m in flagged["metric"]],
            "Current": [f"{r.magnitude:.1f}% {r.side}" for r in flagged.itertuples()],
            "30d avg": [f"{abs(a):.1f}%" if pd.notna(a) else "—"
                        for a in flagged["avg30"]],
            "Δ vs 30d": [f"{c:.1f} pts" if pd.notna(c) else "—"
                         for c in flagged["change"]],
            "Why flagged": flagged["reason"].values,
        })
        st.dataframe(af, width="stretch", hide_index=True,
                     height=min(360, 40 + 35 * len(af)))
        st.caption(f"{len(af)} flag(s) · flagged when the latest asymmetry is over "
                   "15% or has moved ≥10 points from the athlete's 30-day average.")

    st.markdown("---")

    # --- Squad report card (athletes × metrics, scaled 0-100) ---------------
    C.section_label("users", "Squad report card · scaled 0–100 (50 = group mean)")
    all_ath = sorted(tdf["athlete"].dropna().unique())
    default = ath.recently_tested(tdf, 20)
    picked = st.multiselect(
        "Players", all_ath, default=default,
        help="Type to search. Defaults to the 20 most recently tested.")
    perf_metrics = [m for m in metrics if norm.metric_direction(m) != norm.ZERO]
    if not picked:
        st.info("Select players to build the report card.")
    elif not perf_metrics:
        st.info("No performance metrics available.")
    else:
        mat = ath.squad_matrix(tdf, perf_metrics, rep_how, athletes=picked)
        mat = mat.dropna(how="all")
        if mat.empty:
            st.info("No scores for the selected players.")
        else:
            mat["Overall"] = mat.mean(axis=1)
            mat = mat.sort_values("Overall", ascending=False)
            cols = ["Overall"] + [c for c in mat.columns if c != "Overall"]
            mat = mat[cols]
            short = ["Overall"] + [_short(c) for c in mat.columns if c != "Overall"]
            z = mat.values.astype(float)
            fig = go.Figure(go.Heatmap(
                z=z, x=short, y=list(mat.index),
                colorscale=[[0, T.BACKOFF], [0.5, "#2a2a2a"], [1, T.GO]],
                zmin=0, zmid=50, zmax=100,
                text=np.round(z, 0), texttemplate="%{text:.0f}",
                textfont=dict(size=10, color=T.INK),
                hovertemplate="%{y}<br>%{x}: %{z:.0f}/100<extra></extra>",
                colorbar=dict(title="", thickness=10, len=0.6,
                              tickfont=dict(color=T.INK_MUTED, size=10))))
            fig.update_layout(**T.plotly_layout(height=max(320, 30 * len(mat) + 80)))
            fig.update_xaxes(side="top", tickangle=-35, tickfont=dict(size=10))
            C.show_chart(fig)
            st.caption("Green = above group mean · grey = average · red = below. "
                       "Sorted by overall. Hover a cell for the score.")

    st.markdown("---")

    # --- Leaderboard + squad trend ------------------------------------------
    a, b = st.columns([1, 1])
    with a:
        C.section_label("trend", f"Leaderboard · {_short(metric)}")
        if rep.empty:
            st.info("No data.")
        else:
            rep["group"] = rep["group"].fillna("All Athletes")
            top = rep.reindex(
                rep["value"].sort_values(ascending=(direction == "lower")).index).head(12)
            C.show_chart(C.ranking_chart(top, metric, unit, direction,
                                         height=max(280, 26 * len(top))))
            C.legend_bands()
    with b:
        C.section_label("chart", f"Squad trend · monthly {('best' if rep_how=='best' else 'mean')}")
        trend = _monthly_trend(tdf, metric, rep_how)
        if trend.empty:
            st.info("Not enough dated tests.")
        else:
            fig = go.Figure()
            fig.add_scatter(x=trend["month"], y=trend["value"], mode="lines+markers",
                            line=dict(color=T.RED, width=2), marker=dict(color=T.RED, size=7),
                            hovertemplate="%{x|%b %Y}<br>%{y:.1f} " + unit + "<extra></extra>")
            fig.update_layout(**T.plotly_layout(height=300,
                              yaxis_title=f"{_short(metric)} [{unit}]" if unit else metric))
            C.show_chart(fig)


def _recent_tests(tdf, metric, since, direction, rep):
    """Per-session rows for `metric` in the window, with Δ-vs-previous + group band."""
    sub = (tdf[tdf["metric"] == metric].dropna(subset=["value", "test_date"])
           .sort_values(["athlete", "test_date"]).copy())
    if sub.empty:
        return sub
    prev = sub.groupby("athlete")["value"].shift(1)
    sub["pct"] = (sub["value"] - prev) / prev * 100
    rec = sub if since is None else sub[sub["test_date"] >= since]
    rec = rec.copy()
    rec["group"] = rec["group"].fillna("All Athletes")
    repg = rep.copy()
    repg["group"] = repg["group"].fillna("All Athletes")
    stats = {g: norm.group_stats(gg["value"]) for g, gg in repg.groupby("group")}
    rec["z"] = rec.apply(
        lambda r: norm.zscore(r["value"], stats.get(r["group"], {}).get("mean", np.nan),
                              stats.get(r["group"], {}).get("sd", np.nan)), axis=1)
    rec["band"] = rec["z"].apply(lambda z: norm.z_band(z, direction))
    return rec.sort_values("test_date", ascending=False)


def _short(metric: str) -> str:
    """Compact metric label for axes/headers."""
    return (metric.replace("(Imp-Mom)", "").replace("Concentric", "Conc")
            .replace("Eccentric", "Ecc").replace("Impulse", "Imp")
            .replace("Asymmetry", "Asym").replace("  ", " ").strip())


def _monthly_trend(tdf, metric, rep_how):
    sub = tdf[(tdf["metric"] == metric)].dropna(subset=["value", "test_date"])
    if sub.empty:
        return pd.DataFrame()
    agg = "max" if rep_how == "best" else "mean"
    g = (sub.assign(month=sub["test_date"].dt.to_period("M").dt.to_timestamp())
         .groupby("month")["value"].agg(agg).reset_index())
    return g
