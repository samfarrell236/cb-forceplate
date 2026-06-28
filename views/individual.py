"""Individual analysis page — deep dive on one athlete (optionally vs another)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from analysis import normative as norm, athlete as ath, asymmetry as asym, grouping
from ui import components as C, theme as T


def _sw_row(metric, value, band, bar=None):
    """One strength/weakness row: label + value chip + 0-100 bar coloured by band."""
    col = T.BAND_COLORS.get(band, T.INK_MUTED)
    try:
        w = float(bar if bar is not None else value)
    except (TypeError, ValueError):
        w = 0.0
    w = max(0.0, min(100.0, w))
    st.markdown(
        f'<div style="margin:6px 0">'
        f'<div style="display:flex;justify-content:space-between;font-size:12px">'
        f'<span style="color:{T.INK}">{metric}</span>'
        f'<span class="cb-chip" style="color:{col}">{value}</span></div>'
        f'<div style="height:5px;background:{T.RULE};margin-top:3px">'
        f'<div style="height:5px;width:{w}%;background:{col}"></div></div></div>',
        unsafe_allow_html=True,
    )


def _prof_bar(width, chip, band):
    """Thin value bar + value shown under a selectable metric title (tight row)."""
    col = T.BAND_COLORS.get(band, T.INK_MUTED)
    w = max(0.0, min(100.0, float(width) if pd.notna(width) else 0.0))
    st.markdown(
        f'<div style="margin:-14px 0 4px;display:flex;align-items:center;gap:8px">'
        f'<div style="flex:1;height:5px;background:{T.RULE}">'
        f'<div style="height:5px;width:{w}%;background:{col}"></div></div>'
        f'<span style="font-size:11px;font-family:\'JetBrains Mono\',monospace;'
        f'color:{col};min-width:34px;text-align:right">{chip}</span></div>',
        unsafe_allow_html=True,
    )


def _delta_row(metric, cur, delta, suffix="pt"):
    """Row for self-comparison modes: arrow + change, bar = current (centred at 50)."""
    band = "go" if delta > 0.5 else ("backoff" if delta < -0.5 else "maintain")
    col = T.BAND_COLORS[band]
    arrow = "▲" if delta > 0.5 else ("▼" if delta < -0.5 else "▬")
    w = max(0.0, min(100.0, float(cur) if pd.notna(cur) else 0.0))
    sp = "" if suffix == "%" else " "
    st.markdown(
        f'<div style="margin:6px 0">'
        f'<div style="display:flex;justify-content:space-between;font-size:12px">'
        f'<span style="color:{T.INK}">{metric}</span>'
        f'<span class="cb-chip" style="color:{col}">{arrow} {abs(delta):.0f}{sp}{suffix}</span></div>'
        f'<div style="height:5px;background:{T.RULE};margin-top:3px">'
        f'<div style="height:5px;width:{w}%;background:{col}"></div></div></div>',
        unsafe_allow_html=True,
    )


def render(ctx):
    rep_how = ctx.rep_how
    # group the test frame so comparison groups are available (prefer age bands)
    gmode = ("age_band" if ctx.has_birthyear
             else "detected" if ctx.has_group else "all")

    # --- one line: Test · Athlete · Compare vs group -----------------------
    row = st.columns([1.3, 2, 2])
    with row[0]:
        test_type, metrics = C.test_picker(ctx.base, ctx.test_types, ctx.default_test)
    tdf = C.scoped_tdf(ctx, test_type, gmode)
    athletes = sorted(tdf["athlete"].dropna().unique())
    if not athletes:
        st.info("No athletes in this test type.")
        return
    with row[1]:
        C._guard_key("ind_pick", athletes)  # tolerate click-through from Overview
        pick = st.selectbox("Athlete", athletes, key="ind_pick")
    present = [g for g in tdf["group"].unique()
               if g != grouping.UNKNOWN_BAND and isinstance(g, str)]
    groups = (grouping.sort_bands(present) if gmode == "age_band" else sorted(present))
    if "All Athletes" not in groups:
        groups = groups + ["All Athletes"]
    prim = ath.primary_group(tdf, pick)
    default_group = prim if prim in groups else "All Athletes"
    # default the comparison to the athlete's own group; reset when the athlete
    # changes (so each athlete starts compared to their own band).
    if st.session_state.get("_ind_last_athlete") != pick:
        st.session_state["ind_compare_group"] = default_group
        st.session_state["_ind_last_athlete"] = pick
    C._guard_key("ind_compare_group", groups)
    if st.session_state.get("ind_compare_group") not in groups:
        st.session_state["ind_compare_group"] = default_group
    with row[2]:
        compare = st.selectbox("Compare vs group", groups, key="ind_compare_group")
    show = [pick]

    # --- 5 selectable metric cards: latest value + 30-day-avg trend ---------
    C.section_label("scale", f"{pick} · latest test")
    ordered = C.ordered_perf_metrics(metrics)
    ncards = min(5, len(ordered)) or 1
    ccols = st.columns(ncards)
    card_metrics = []
    for i in range(ncards):
        with ccols[i]:
            cm = C.metric_card(tdf, metrics, pick, f"ind_card_{i}",
                               ordered[i] if i < len(ordered) else metrics[0])
            if cm:
                card_metrics.append(cm)
    primary = card_metrics[0] if card_metrics else (ordered[0] if ordered else None)

    # --- Strengths & Weaknesses radar — selectable metric titles on the right -
    mode = st.radio(
        "Comparison", ["Player vs group", "Recent vs all-time", "Latest vs recent"],
        horizontal=True, key="ind_sw_mode",
        help="Recent = last 30 days · all-time = full history · latest = most recent test.")
    self_mode = mode != "Player vs group"
    mk = "recent_alltime" if mode == "Recent vs all-time" else "latest_recent"
    ref_lbl, cur_lbl = (("All-time", "Recent (30d)") if mk == "recent_alltime"
                        else ("Recent (30d)", "Latest"))
    C.section_label("chart", (f"Form profile · {cur_lbl} vs {ref_lbl}" if self_mode
                              else f"Strengths & weaknesses · vs {compare}"))

    perf_all = C.ordered_perf_metrics(metrics)
    n = min(8, len(perf_all))
    radar_h = max(480, 54 * n + 90)
    rcol, scol = st.columns([2, 1], gap="medium", vertical_alignment="center")

    # Right: one selectable title per metric slot + its value bar (all metrics).
    rows = []
    with scol:
        st.markdown('<div class="cb-label" style="margin:2px 0 6px">Metrics '
                    '<span style="color:#555">· tap a title to change</span></div>',
                    unsafe_allow_html=True)
        for i in range(n):
            C._guard_key(f"ind_prof_{i}", perf_all)
            default_i = perf_all[i] if i < len(perf_all) else perf_all[0]
            m = st.selectbox(f"prof{i}", perf_all, index=perf_all.index(default_i),
                             key=f"ind_prof_{i}", label_visibility="collapsed")
            if self_mode:
                p = ath.comparison_profile(tdf, pick, [m], mk)
                if p.empty:
                    _prof_bar(50, "—", "go")
                    continue
                ratio = float(p["cur"].iloc[0])
                delta = ratio - 100.0
                d = norm.metric_direction(m)
                deficit = (ratio - 100.0) if d == "lower" else (100.0 - ratio)
                _prof_bar(50 + delta, f"{delta:+.0f}%", norm.deficit_band(deficit))
                rows.append(dict(metric=m, ref=100.0, cur=ratio))
            else:
                p = ath.profile_scores(tdf, pick, [m], rep_how, ref_group=compare)
                if p.empty:
                    _prof_bar(0, "—", "go")
                    continue
                score = float(p["score"].iloc[0])
                band = norm.deficit_band(float(p["deficit"].iloc[0]))
                _prof_bar(0 if pd.isna(score) else score,
                          "—" if pd.isna(score) else f"{score:.0f}", band)
                rows.append(dict(metric=m, score=score))

    # Left: radar from the selected metrics.
    prof = pd.DataFrame(rows).drop_duplicates("metric") if rows else pd.DataFrame()
    with rcol:
        if self_mode:
            pr = prof.dropna(subset=["cur"]) if not prof.empty else prof
            fig, ok = C.radar_from_frame(pr, [
                ("ref", f"{ref_lbl} (baseline)", T.INK_MUTED, None),
                ("cur", cur_lbl, T.RED, "rgba(200,16,46,0.18)")],
                height=radar_h, radial_range=(50, 150),
                hover_suffix="%") if not pr.empty else (None, False)
            C.show_chart(fig) if ok else st.info("Pick at least 3 metrics with data.")
        else:
            pr = prof.dropna(subset=["score"]) if not prof.empty else prof
            if not pr.empty:
                rad = pr[["metric", "score"]].copy()
                rad["baseline"] = 50
                fig, ok = C.radar_from_frame(rad, [
                    ("baseline", f"{compare} avg", T.INK_MUTED, None),
                    ("score", pick, T.RED, "rgba(200,16,46,0.18)")], height=radar_h)
                C.show_chart(fig) if ok else st.caption("Pick at least 3 metrics.")
            else:
                st.caption("Pick at least 3 metrics for a radar.")
    st.caption(
        (f"Each metric as a % of {ref_lbl.lower()} (centred baseline = 100%) · "
         f"green = {cur_lbl.lower()} above, red = below."
         if self_mode else
         f"Scaled 0–100 vs {compare} · 50 = group average · green = above, red = below."))

    # trend over time — the athlete's own series, with its own metric + timeline
    C.section_label("trend", "Trend over time")
    tc = st.columns([2, 2, 4])
    with tc[0]:
        tmetric, tunit, _, _ = C.metric_picker(tdf, metrics, "ind_trend_metric",
                                               default=primary)
    with tc[1]:
        twin = st.selectbox("Timeline", ["Last 90 days", "Last 6 months",
                            "Last 12 months", "Last 2 years", "All time"],
                            index=4, key="ind_trend_win")
    days = {"Last 90 days": 90, "Last 6 months": 182, "Last 12 months": 365,
            "Last 2 years": 730}.get(twin)
    wtdf = tdf
    if days and tmetric:
        sd = tdf[(tdf["athlete"] == pick) & (tdf["metric"] == tmetric)]["test_date"]
        if not sd.empty and pd.notna(sd.max()):
            wtdf = tdf[tdf["test_date"] >= sd.max().normalize() - pd.Timedelta(days=days)]
    if tmetric:
        C.show_chart(C.trend_chart(wtdf, [pick], tmetric, tunit))

    # all-metrics latest vs comparison group
    C.section_label("trend", f"All metrics · latest vs {compare}")
    lv = ath.latest_vs_norm(tdf, pick, rep_how, ref_group=compare)
    if not lv.empty:
        view = lv[["metric", "value", "unit", "group_mean", "z", "percentile", "band"]].rename(
            columns={"metric": "Metric", "value": "Value", "unit": "Unit",
                     "group_mean": "Group mean", "z": "Z", "percentile": "Pct",
                     "band": "Status"})
        st.dataframe(view.style.format({"Value": "{:.1f}", "Group mean": "{:.1f}",
                                        "Z": "{:+.2f}", "Pct": "{:.0f}"}),
                     width="stretch", hide_index=True)

    # athlete asymmetry
    asym_mets = asym.asymmetry_metrics(tdf)
    if asym_mets:
        C.section_label("alert", "Asymmetry · this athlete")
        rows = []
        for amet in asym_mets:
            fa = asym.flag_asymmetries(tdf, ctx.asym_threshold, rep_how)
            r = fa[(fa["metric"] == amet) & (fa["athlete"] == pick)]
            if not r.empty:
                rr = r.iloc[0]
                rows.append(dict(Metric=amet, Asym=f'{abs(rr["value"]):.1f} {rr["side"]}',
                                 Magnitude=rr["magnitude"], Over=rr["flagged"]))
        if rows:
            adf = pd.DataFrame(rows)
            cols = st.columns([3, 1])
            with cols[0]:
                st.dataframe(adf.style.format({"Magnitude": "{:.1f}"}),
                             width="stretch", hide_index=True)
            with cols[1]:
                worst = adf["Magnitude"].max()
                C.tile("Worst |asym|", C.fmt(worst), "%",
                       "flagged" if (adf["Over"]).any() else "within")

    # test history
    with st.expander("Test history (all sessions)"):
        hist = (tdf[tdf["athlete"] == pick]
                .pivot_table(index="test_date", columns="metric", values="value",
                             aggfunc="first")
                .sort_index(ascending=False))
        if not hist.empty:
            hist.index = hist.index.strftime("%Y-%m-%d %H:%M")
            st.dataframe(hist.style.format("{:.1f}"), width="stretch")
